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

#include <memory>

#include <boost/filesystem.hpp>

namespace ibe
{
bool cutoutPixelBox (Coords center, Coords size, char *hdr,
                     long const *naxis, long *box);

size_t write_header_end(Writer &writer, size_t num_bytes)
{
  unsigned char block[2880];

  // write the END header card
  writer.write (reinterpret_cast<const unsigned char *>("END"), 3);
  num_bytes += 3;
  // pad header with spaces till its size is a multiple of 2880.
  if ((num_bytes % sizeof(block)) != 0)
    {
      size_t n = sizeof(block) - (num_bytes % sizeof(block));
      std::memset (block, static_cast<int>(' '), n);
      writer.write (block, n);
      num_bytes += n;
    }
  return num_bytes;
}

void stream_subimage (boost::filesystem::path const &path,
                      Coords const &center, Coords const &size, Writer &writer)
{
  unsigned char block[2880];
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
      fits_get_hdrspace (f, &nkeys, NULL, &status);
      checkFitsError (status);
      if (hdutype != IMAGE_HDU)
        {
          // Copy the HDU. First copy the header, stripping away space
          // reserved for additional header keywords.
          for (int k = 1; k <= nkeys; ++k)
            {
              fits_read_record (f, k, card, &status);
              checkFitsError (status);
              for (size_t i = strlen (card); i < 80; ++i)
                {
                  card[i] = ' ';
                }
              writer.write (reinterpret_cast<unsigned char *>(card), 80u);
              numBytes += 80;
            }
          numBytes = write_header_end(writer, numBytes);
          // Copy the data.
          LONGLONG data_start, data_end;
          fits_get_hduaddrll (f,  NULL, &data_start, &data_end, &status);
          checkFitsError (status);
          long num_blocks = static_cast<long>((data_end - data_start) / 2880);
          if (num_blocks > 0)
            {
              // Move to the initial copy position
              ffmbyt (f, data_start, REPORT_EOF, &status);
              checkFitsError (status);
              for (long b = 0; b < num_blocks; b++)
                {
                  // Read input block
                  ffgbyt (f, sizeof(block), block, &status);
                  checkFitsError (status);
                  writer.write (block, sizeof(block));
                  numBytes += sizeof(block);
                }
            }
          continue;
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
          std::shared_ptr<char> h (hdr, std::free);
          checkFitsError (status);
          // 2. Compute coordinate box for cutout
          if (!cutoutPixelBox (center, size, hdr, naxis, box))
            {
              // no overlap
              throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                                 "Cutout does not overlap image");
            }
        }

      // copy keywords from the input to the writer, but modify
      // NAXIS1, NAXIS2, LTV1, LTV2, CRPIX1, CRPIX2, CRPIX1Axx, CRPIX2Axx
      // to account for the subimage operation along the way.
      for (int k = 1; k <= nkeys; ++k)
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
      numBytes = write_header_end(writer, numBytes);
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
      std::shared_ptr<void> buf (std::malloc (bufsz), std::free);
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
      if ((numBytes % sizeof(block)) != 0)
        {
          size_t nb = sizeof(block) - (numBytes % sizeof(block));
          std::memset (block, 0, nb);
          writer.write (block, nb);
          numBytes += nb;
        }
    }
}
}
