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

namespace
{
constexpr int FITS_CARD_LENGTH = 80;
constexpr int FITS_BLOCK_LENGTH = 2880;

size_t end_header(Writer &writer, size_t num_bytes, bool write_end_card)
{
  unsigned char block[FITS_BLOCK_LENGTH];
  if (write_end_card)
    {
      writer.write (reinterpret_cast<const unsigned char *>("END"), 3);
      num_bytes += 3;
    }
  // pad header with spaces till its size is a multiple of the block size.
  if ((num_bytes % sizeof(block)) != 0)
    {
      size_t n = sizeof(block) - (num_bytes % sizeof(block));
      std::memset (block, static_cast<int>(' '), n);
      writer.write (block, n);
      num_bytes += n;
    }
  return num_bytes;
}

// Copy HDU header, removing any space reserved for additional keywords.
size_t copy_header(FitsFile &f, Writer &writer, size_t num_bytes)
{
  char card[FLEN_CARD];
  int status = 0;
  int nkeys = 0;
  fits_get_hdrspace (f, &nkeys, NULL, &status);
  for (int k = 1; k <= nkeys; ++k)
    {
      fits_read_record (f, k, card, &status);
      checkFitsError (status);
      for (size_t i = strlen (card); i < FITS_CARD_LENGTH; ++i)
        {
          card[i] = ' ';
        }
      writer.write (reinterpret_cast<unsigned char *>(card), FITS_CARD_LENGTH);
      num_bytes += FITS_CARD_LENGTH;
    }
  return end_header(writer, num_bytes, true);
}

// Copy current HDU data.
size_t copy_data(FitsFile &f, Writer &writer, size_t num_bytes)
{
  unsigned char block[FITS_BLOCK_LENGTH];
  LONGLONG data_start;
  LONGLONG data_end;
  int status = 0;

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
          num_bytes += sizeof(block);
        }
    }
  return num_bytes;
}

void parse_card(char *hdr, char *keyname, char *valstring, char *comment)
{
  char card[FLEN_CARD];
  int namelen;
  int status = 0;
  keyname[0] = '\0';
  valstring[0] = '\0';
  comment[0] = '\0';
  // Pass null terminated cards with no trailing blanks to CFITSIO routines.
  std::memcpy(card, hdr, FITS_CARD_LENGTH);
  for (int i = FITS_CARD_LENGTH;; --i)
    {
      if (i == 0)
        {
          card[0] = '\0';
          break;
        }
      if (card[i - 1] != ' ')
        {
          card[i] = '\0';
          break;
        }
    }
  fits_get_keyname (card, keyname, &namelen, &status);
  checkFitsError (status);
  fits_parse_value (card, valstring, comment, &status);
  checkFitsError (status);
  fits_test_record (keyname, &status);
  checkFitsError (status);
}

size_t write_card(Writer &writer, size_t num_bytes,
                  const char *keyname, const char *value, const char *comment)
{
  char card[FLEN_CARD];
  char valstring[FLEN_VALUE];
  int status = 0;

  strncpy(valstring, value, sizeof(valstring) - 1);
  valstring[sizeof(valstring) - 1] = '\0';
  ffmkky (keyname, valstring, comment, card, &status);
  checkFitsError (status);
  for (size_t i = std::strlen (card); i < FITS_CARD_LENGTH; ++i)
    {
      card[i] = ' ';
    }
  writer.write(reinterpret_cast<unsigned char *>(card), FITS_CARD_LENGTH);
  return num_bytes + FITS_CARD_LENGTH;
}

// CFITSIO image reads map pixel values, stored in big-endian byte order,
// to C datatypes. On little endian systems, this must be undone before
// writing pixels back out.
void bswap_pixels(void *buf, size_t buf_size, int bitpix)
{
#if __BYTE_ORDER == __LITTLE_ENDIAN
  switch (bitpix)
    {
    case 16:
      {
        uint16_t *b = static_cast<uint16_t *>(buf);
        for (size_t i = 0; i < buf_size / 2; ++i)
          {
            uint16_t v = b[i];
            b[i] = (v >> 8) | (v << 8);
          }
      }
      break;
    case 32:
    case -32:
      {
        int32_t *b = static_cast<int32_t *>(buf);
        for (size_t i = 0; i < buf_size / 4; ++i)
          {
            b[i] = __builtin_bswap32 (b[i]);
          }
        break;
      }
    case 64:
    case -64:
      {
        int64_t *b = static_cast<int64_t *>(buf);
        for (size_t i = 0; i < buf_size / 8; ++i)
          {
            b[i] = __builtin_bswap64 (b[i]);
          }
        break;
      }
    default:
      break;
    }
#endif
}

size_t write_subimage(FitsFile &f, Writer &writer, const long *naxis,
                      const long *box, int bitpix, size_t num_bytes)
{
  unsigned char block[FITS_BLOCK_LENGTH];
  int status = 0;
  int anynul;
  int datatype;

  // Turn off any pixel value scaling. Because FITS implements unsigned
  // integer types as signed integers of the same size with an offset
  // (BZERO), this allows unsigned integer datatypes to be ignored in
  // what follows.
  fits_set_bscale (f, 1.0, 0.0, &status);
  checkFitsError (status);
  // Determine FITS datatype of pixels.
  switch (bitpix)
    {
    case 8:
      datatype = TBYTE;
      break;
    case 16:
      datatype = TSHORT;
      break;
    case 32:
      datatype = TINT;
      break;
    case -32:
      datatype = TFLOAT;
      break;
    case 64:
      datatype = TLONGLONG;
      break;
    case -64:
      datatype = TDOUBLE;
      break;
    default:
      throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "Invalid BITPIX value in image HDU");
    }

  if (!fits_is_compressed_image(f, &status))
    {
      // Write out subimage one row at a time.
      size_t buf_size = static_cast<size_t>(box[2] - box[0] + 1) *
                     (std::abs (bitpix) / 8);
      std::shared_ptr<void> buf (std::malloc (buf_size), std::free);
      if (!buf)
        {
          throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                            "Memory allocation failed");
        }
      LONGLONG firstpix = box[0] + naxis[0] * (box[1] - 1);
      LONGLONG nelem = box[2] - box[0] + 1;
      for (long y = box[1]; y <= box[3]; ++y, firstpix += naxis[0])
        {
          fits_read_img (f, datatype, firstpix, nelem, nullptr, buf.get(),
                         &anynul, &status);
          checkFitsError (status);
          bswap_pixels (buf.get(), buf_size, bitpix);
          writer.write (static_cast<unsigned char *>(buf.get ()), buf_size);
          num_bytes += buf_size;
        }
    }
  else
    {
      // Reading a subset of a tile compressed image row by row, as is done
      // for uncompressed images, is very slow. (Hypothesis: because a tile
      // that contributes to N output rows is decompressed N times). Use a
      // dedicated CFITSIO routine instead, at the cost of allocating memory
      // for the entire subimage.
      long ininc[2] = {1, 1};
      LONGLONG infpixel[2] = {box[0], box[1]};
      LONGLONG inlpixel[2] = {box[2], box[3]};
      size_t buf_size = static_cast<size_t>(box[2] - box[0] + 1) *
                        static_cast<size_t>(box[3] - box[1] + 1) *
                        (std::abs (bitpix) / 8);
      std::shared_ptr<void> buf (std::malloc (buf_size), std::free);
      if (!buf)
        {
          throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                            "Memory allocation failed");
        }
      fits_read_compressed_img (f, datatype, infpixel, inlpixel, ininc, 0,
                                nullptr, buf.get(), nullptr, &anynul, &status);
      checkFitsError (status);
      bswap_pixels (buf.get(), buf_size, bitpix);
      writer.write (static_cast<unsigned char *>(buf.get ()), buf_size);
      num_bytes += buf_size;
    }
  // Finally, write out zeros so the output HDU is a multiple of the block size.
  if ((num_bytes % sizeof(block)) != 0)
    {
      size_t n = sizeof(block) - (num_bytes % sizeof(block));
      std::memset (block, 0, n);
      writer.write (block, n);
      num_bytes += n;
    }
  return num_bytes;
}
}

bool cutoutPixelBox (Coords center, Coords size, char *hdr,
                     long const *naxis, long *box);

void stream_subimage (boost::filesystem::path const &path,
                      Coords const &center, Coords const &size, Writer &writer)
{
  char keyname[FLEN_KEYWORD];
  char valstring[FLEN_VALUE];
  char comment[FLEN_COMMENT];
  long naxis[2] = { 0L, 0L };
  long box[4] = { 0L, 0L, 0L, 0L };
  int status = 0;
  int hdutype = 0;
  int bitpix = 0;
  int naxes = 0;
  int nkeys = 0;
  char *hdr = nullptr;
  size_t num_bytes = 0;

  FitsFile f (path.string ().c_str ());

  // Loop over all HDUs.
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
          // Copy the HDU.
          num_bytes = copy_header(f, writer, num_bytes);
          // Copy the data.
          num_bytes = copy_data(f, writer, num_bytes);
          continue;
        }
      fits_get_img_param (f, 2, &bitpix, &naxes, naxis, &status);
      checkFitsError (status);
      if (naxes == 0)
        {
          // No data - just copy the header.
          num_bytes = copy_header(f, writer, num_bytes);
          continue;
        }
      // For now, just handle 2 dimensional images.
      if (naxes != 2 || naxis[0] <= 0 || naxis[1] <= 0)
        {
          throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                              "FITS file contains image HDU with "
                              "NAXIS != 2");
        }

      // Read all header keywords, and compute cutout coordinate box
      nkeys = 0;
      hdr = nullptr;
      // Unlike fits_get_hdrspace, nkeys returned by fits_convert_hdr2str includes the
      // END card. It also converts the header for a tile-compressed image HDU to a
      // regular image header. The result of such a conversion will always be a header
      // for a primary HDU, which must be munged to turn it into a valid extension header.
      fits_convert_hdr2str (f, 0, NULL, 0, &hdr, &nkeys, &status);
      std::shared_ptr<char> h (hdr, std::free);
      checkFitsError (status);
      if (!cutoutPixelBox (center, size, hdr, naxis, box))
        {
          // no overlap between cutout box and image
          throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                              "Cutout does not overlap image");
        }
      bool is_compressed_image = fits_is_compressed_image(f, &status);
      checkFitsError (status);
      if (is_compressed_image)
        {
          // Replace SIMPLE card with EXTENSION card
          num_bytes = write_card (writer, num_bytes,
                                  "XTENSION", "'IMAGE   '", "IMAGE extension");
          hdr += FITS_CARD_LENGTH;
          nkeys -= 1;
        }

      // Copy keywords from the input to the writer, but modify
      // NAXIS1, NAXIS2, LTV1, LTV2, CRPIX1, CRPIX2, CRPIX1Axx, CRPIX2Axx
      // to account for the subimage operation along the way.
      for (int k = 0; k < nkeys; ++k, hdr += FITS_CARD_LENGTH)
        {
          if (is_compressed_image)
            {
              // Skip EXTEND card and reference comments
              if (strncmp(hdr, "EXTEND  ", 8) == 0 ||
                  strncmp(hdr, "COMMENT   FITS (Flexible Image Transport System) format is", 58) == 0 ||
                  strncmp(hdr, "COMMENT   and Astrophysics', volume 376, page 3", 47) == 0)
                {
                  continue;
                }
              // Skip PCOUNT and GCOUNT cards, since they are added in explicitly
              if (strncmp(hdr, "PCOUNT  ", 8) == 0 ||
                  strncmp(hdr, "GCOUNT  ", 8) == 0)
                {
                  continue;
                }
            }
          // Drop CHECKSUM and DATASUM keywords, since their values will no longer
          // be correct for the subimage.
          if (strncmp(hdr, "CHECKSUM", 8) == 0 ||
              strncmp(hdr, "DATASUM ", 8) == 0)
            {
              continue;
            }
          bool modified = false;
          bool found_naxis2 = false;
          parse_card(hdr, keyname, valstring, comment);

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
                  found_naxis2 = (keyname[5] == '2');
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

          if (modified)
            {
              num_bytes = write_card (writer, num_bytes, keyname, valstring, comment);
              if (is_compressed_image && found_naxis2)
                {
                  // Add in PCOUNT and GCOUNT cards after NAXIS2
                  num_bytes = write_card (writer, num_bytes, "PCOUNT", "0",
                                          "number of random group parameters");
                  num_bytes = write_card (writer, num_bytes, "GCOUNT", "1",
                                          "number of random groups");
                }
            }
          else
            {
              writer.write (reinterpret_cast<unsigned char *>(hdr), FITS_CARD_LENGTH);
              num_bytes += FITS_CARD_LENGTH;
            }
        }
      num_bytes = end_header(writer, num_bytes, false);
      num_bytes = write_subimage(f, writer, naxis, box, bitpix, num_bytes);
    }
}
}
