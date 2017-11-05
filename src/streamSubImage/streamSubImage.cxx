#include "../checkFitsError.hxx"
#include "../FitsFile.hxx"
#include "../Coords.hxx"
#include "../Cgi.hxx"

#include <endian.h>
#include <stdint.h>
#if __BYTE_ORDER == __LITTLE_ENDIAN
#include <byteswap.h>
#elif __BYTE_ORDER != __BIG_ENDIAN
#error Unknown byte order!
#endif

#include <boost/filesystem.hpp>

namespace ibe
{
bool cutoutPixelBox (Coords center, Coords size, char *hdr, int nkeys,
                     long const *naxis, long *box);

void streamSubimage (boost::filesystem::path const &path, Coords const &center,
                     Coords const &size, Writer &writer)
{
  unsigned char padding[2880];
  char keyname[FLEN_KEYWORD];
  char valstring[FLEN_VALUE];
  char comment[FLEN_COMMENT];
  char card[FLEN_CARD];
  long naxis[2] = { 0L, 0L };
  long box[4] = { 0L, 0L, 0L, 0L };
  int status = 0;
  int hdutype = 0;
  int bitpix = 0;
  int naxes = 0;
  int nkeys = 0;
  char *hdr = 0;
  size_t numBytes = 0;

  // open on-disk file
  FitsFile f (path.string ().c_str ());

  // loop over all HDUs.
  // FIXME: deal with INHERIT keyword
  for (int hdunum = 1;; ++hdunum)
    {
      fits_movabs_hdu (f, hdunum, &hdutype, &status);
      if (status == END_OF_FILE)
        {
          // looped over all HDUs
          break;
        }
      checkFitsError (status);
      if (hdutype != IMAGE_HDU)
        {
          throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                             "FITS file contains non-image HDU");
        }
      fits_get_img_param (f, 2, &bitpix, &naxes, naxis, &status);
      checkFitsError (status);
      if (naxes != 0)
        {
          // Determine cutout pixel box for the HDU
          if (naxes != 2 || naxis[0] <= 0 || naxis[1] <= 0)
            {
              throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                                 "FITS file contains image HDU with "
                                 "NAXIS != 2");
            }
          // 1. Read all header keywords
          nkeys = 0;
          hdr = 0;
          fits_convert_hdr2str (f, 0, NULL, 0, &hdr, &nkeys, &status);
          boost::shared_ptr<char> h (hdr, std::free);
          checkFitsError (status);
          // 2. Compute coordinate box for cutout
          if (!cutoutPixelBox (center, size, hdr, nkeys, naxis, box))
            {
              // no overlap
              throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                                 "Cutout does not overlap image");
            }
        }

      // copy keywords from the input to the writer, but modify
      // NAXIS1, NAXIS2, LTV1, LTV2, CRPIX1, CRPIX2, CRPIX1Axx, CRPIX2Axx
      // to account for the subimage operation along the way.
      fits_get_hdrspace (f, &nkeys, NULL, &status);
      checkFitsError (status);
      for (int k = 1; k <= nkeys + 1; ++k)
        {
          bool modified = false;
          if (naxes != 0)
            {
              fits_read_keyn (f, k, keyname, valstring, comment, &status);
              checkFitsError (status);
              if (strncmp (keyname, "NAXIS", 5) == 0)
                {
                  if (keyname[6] == '\0'
                      && (keyname[5] == '1' || keyname[5] == '2'))
                    {
                      int axis = keyname[5] - '1';
                      long naxis = box[2 + axis] - box[axis] + 1;
                      ffi2c (naxis, valstring, &status);
                      checkFitsError (status);
                      modified = true;
                    }
                }
              else if (strncmp (keyname, "LTV", 3) == 0)
                {
                  if (keyname[4] == '\0'
                      && (keyname[3] == '1' || keyname[3] == '2'))
                    {
                      int axis = keyname[3] - '1';
                      double ltv = 0.0;
                      ffc2d (valstring, &ltv, &status);
                      checkFitsError (status);
                      ltv += box[axis] - 1;
                      ffd2e (ltv, 15, valstring, &status);
                      checkFitsError (status);
                      modified = true;
                    }
                }
              else if (strncmp (keyname, "CRPIX", 5) == 0)
                {
                  if ((keyname[5] == '1' || keyname[5] == '2')
                      && (keyname[6] == '\0'
                          || (keyname[6] >= 'A' && keyname[6] <= 'Z'
                              && keyname[7] == '\0')))
                    {
                      int axis = keyname[5] - '1';
                      double crpix = 0.0;
                      ffc2d (valstring, &crpix, &status);
                      checkFitsError (status);
                      crpix += 1 - box[axis];
                      ffd2e (crpix, 15, valstring, &status);
                      checkFitsError (status);
                      modified = true;
                    }
                }
            }
          if (modified)
            {
              ffmkky (keyname, valstring, comment, card, &status);
              checkFitsError (status);
            }
          else
            {
              fits_read_record (f, k, card, &status);
              checkFitsError (status);
            }
          for (size_t i = strlen (card); i < 80; ++i)
            {
              card[i] = ' ';
            }
          writer.write (reinterpret_cast<unsigned char *>(card), 80u);
          numBytes += 80;
        }
      if ((numBytes % 2880) != 0)
        {
          // pad header with spaces till its size is a multiple of 2880.
          size_t nb = 2880 - (numBytes % 2880);
          std::memset (padding, static_cast<int>(' '), nb);
          writer.write (padding, nb);
          numBytes += nb;
        }
      if (naxes == 0)
        {
          // No image data
          continue;
        }
      // turn off any pixel value scaling
      fits_set_bscale (f, 1.0, 0.0, &status);
      checkFitsError (status);

      // allocate memory for one pixel row
      long rowsz = box[2] - box[0] + 1;
      size_t bufsz = static_cast<size_t>(rowsz) * std::abs (bitpix) / 8;
      boost::shared_ptr<void> buf (std::malloc (bufsz), std::free);
      if (!buf)
        {
          throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                             "Memory allocation failed");
        }
      LONGLONG firstpix = box[0] + naxis[0] * (box[1] - 1);
      int anynul = 0;
      // copy one row of the input to the output at a time
      for (long y = box[1]; y <= box[3]; ++y, firstpix += naxis[0])
        {
          switch (bitpix)
            {
            case 8:
              fits_read_img_byt (f, 0, firstpix, rowsz, 0,
                                 static_cast<unsigned char *>(buf.get ()),
                                 &anynul, &status);
              checkFitsError (status);
              break;
            case 16:
              fits_read_img_sht (f, 0, firstpix, rowsz, 0,
                                 static_cast<short *>(buf.get ()), &anynul,
                                 &status);
              checkFitsError (status);
#if __BYTE_ORDER == __LITTLE_ENDIAN
              {
                uint16_t *b = static_cast<uint16_t *>(buf.get ());
                for (long j = 0; j < rowsz; ++j)
                  {
                    uint16_t v = b[j];
                    b[j] = (v >> 8) | (v << 8);
                  }
              }
#endif
              break;
            case 32:
              fits_read_img_int (f, 0, firstpix, rowsz, 0,
                                 static_cast<int *>(buf.get ()), &anynul,
                                 &status);
              checkFitsError (status);
#if __BYTE_ORDER == __LITTLE_ENDIAN
              {
                int32_t *b = static_cast<int32_t *>(buf.get ());
                for (long j = 0; j < rowsz; ++j)
                  {
                    b[j] = __builtin_bswap32 (b[j]);
                  }
              }
#endif
              break;
            case -32:
              fits_read_img_flt (f, 0, firstpix, rowsz, 0.0,
                                 static_cast<float *>(buf.get ()), &anynul,
                                 &status);
              checkFitsError (status);
#if __BYTE_ORDER == __LITTLE_ENDIAN
              {
                int32_t *b = static_cast<int32_t *>(buf.get ());
                for (long j = 0; j < rowsz; ++j)
                  {
                    b[j] = __builtin_bswap32 (b[j]);
                  }
              }
#endif
              break;
            case 64:
              fits_read_img_lnglng (f, 0, firstpix, rowsz, 0,
                                    static_cast<LONGLONG *>(buf.get ()),
                                    &anynul, &status);
              checkFitsError (status);
#if __BYTE_ORDER == __LITTLE_ENDIAN
              {
                int64_t *b = static_cast<int64_t *>(buf.get ());
                for (long j = 0; j < rowsz; ++j)
                  {
                    b[j] = __builtin_bswap64 (b[j]);
                  }
              }
#endif
              break;
            case -64:
              fits_read_img_dbl (f, 0, firstpix, rowsz, 0.0,
                                 static_cast<double *>(buf.get ()), &anynul,
                                 &status);
              checkFitsError (status);
#if __BYTE_ORDER == __LITTLE_ENDIAN
              {
                int64_t *b = static_cast<int64_t *>(buf.get ());
                for (long j = 0; j < rowsz; ++j)
                  {
                    b[j] = __builtin_bswap64 (b[j]);
                  }
              }
#endif
              break;
            default:
              throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                                 "Invalid BITPIX value in image HDU");
            }
          writer.write (static_cast<unsigned char *>(buf.get ()), bufsz);
          numBytes += bufsz;
        }
      if ((numBytes % 2880) != 0)
        {
          size_t nb = 2880 - (numBytes % 2880);
          std::memset (padding, 0, nb);
          writer.write (padding, nb);
          numBytes += nb;
        }
    }
}
}
