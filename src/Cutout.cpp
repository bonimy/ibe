/** @file
 * @brief  FITS image cutout implementation.
 * @author Serge Monkewitz
 */
#include "Cutout.h"

#include <endian.h>
#include <stdint.h>
#if __BYTE_ORDER == __LITTLE_ENDIAN
#include <byteswap.h>
#elif __BYTE_ORDER != __BIG_ENDIAN
#error Unknown byte order!
#endif

#include "boost/algorithm/string/predicate.hpp"
#include "boost/regex.hpp"
#include "boost/shared_ptr.hpp"

using std::string;

namespace ibe
{

// == Helper functions ----

namespace
{

// Check if CFITSIO has failed and throw an internal server error if so.
void
checkFitsError (int status)
{
  char statMsg[32];
  char errMsg[96];
  if (status != 0)
    {
      fits_get_errstatus (status, statMsg);
      if (fits_read_errmsg (errMsg) != 0)
        {
          throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                             format ("%s : %s", statMsg, errMsg));
        }
      throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR, statMsg);
    }
}

// Return the angular separation in radians between 2 vectors in R3.
inline double
dist (const double *v1, const double *v2)
{
  double cs = v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2];
  double x = v1[1] * v2[2] - v1[2] * v2[1];
  double y = v1[2] * v2[0] - v1[0] * v2[2];
  double z = v1[0] * v2[1] - v1[1] * v2[0];
  double ss = sqrt (x * x + y * y + z * z);
  return ((ss != 0.0) || (cs != 0.0)) ? std::atan2 (ss, cs) : 0.0;
}

// Convert spherical coordinates (deg) to a vector in R3.
inline void
s2c (const double *sky, double *v)
{
  v[0] = std::cos (RAD_PER_DEG * sky[0]) * std::cos (RAD_PER_DEG * sky[1]);
  v[1] = std::sin (RAD_PER_DEG * sky[0]) * std::cos (RAD_PER_DEG * sky[1]);
  v[2] = std::sin (RAD_PER_DEG * sky[1]);
}

// Return the center coordinate of the pixel containing x, FITS conventions.
// Pixel N has center coordinate N, and spans [N - 0.5, N + 0.5).
inline double
pixcen (double x)
{
  return std::floor (x + 0.5);
}

// Return the closest x or y coordinate separated by at least size radians from
// the given center in the given direction.
double search (Wcs &wcs,            // WCS for 2D image to search
               const double sky[2], // center to search outwards from
               const double pix[2], // pixel coordinates of sky
               const double size,   // desired size in radians
               const int dim,       // axis to search along: 0 (x) or 1 (y)
               const int dir)       // direction to search along: +1 or -1
{
  double cen[3], v[3], p[2], s[2], d, inc, scale;
  s2c (sky, cen);
  inc = dir;
  p[!dim] = pix[!dim];
  p[dim] = pixcen (pix[dim]) + 0.5 * inc;
  scale = 2.0;
  while (std::fabs (inc) >= 1.0 && !std::isinf (p[0]) && !std::isinf (p[1]))
    {
      wcs.pixelToSky (p, s);
      s2c (s, v);
      d = dist (cen, v);
      if (d < size)
        {
          inc *= scale;
          p[dim] += inc;
        }
      else if (d > size)
        {
          scale = 0.5;
          inc *= 0.5;
          p[dim] -= inc;
        }
      else
        {
          break;
        }
    }
  return pixcen (p[dim]);
}

// Map the given center and size to a pixel-space box for a cutout. If the
// requested cutout doesn't overlap the image, \c false is returned. Results
// are
// stored in \c box as follows: box[0] = xmin, box[1] = ymin, box[2] = xmax,
// box[3] = ymax.
bool
cutoutPixelBox (Coords center, // Cutout center.
                Coords size,   // Cutout size.
                char *hdr,     // FITS header string (as returned by CFITSIO).
                int nkeys,     // Number of FITS header cards.
                long const *naxis, // Image dimensions (NAXIS1 and  NAXIS2).
                long *box) // Pixel-space cutout box; must point to an array of
                           // at least 4 longs.
{
  double xmin, xmax, ymin, ymax;
  if (center.units != PIX || size.units != PIX)
    {
      // need to map center and/or size to pixel coordinates
      Wcs wcs (hdr, nkeys);
      double sky[2];
      if (center.units == PIX)
        {
          wcs.pixelToSky (center.c, sky);
        }
      else
        {
          // convert to degrees
          switch (center.units)
            {
            case ARCSEC:
              center.c[0] /= 3600.0;
              center.c[1] /= 3600.0;
              break;
            case ARCMIN:
              center.c[0] /= 60.0;
              center.c[1] /= 60.0;
              break;
            case RAD:
              center.c[0] *= DEG_PER_RAD;
              center.c[1] *= DEG_PER_RAD;
              break;
            default:
              break;
            }
          if (center.c[1] < -90.0 || center.c[1] > 90.0)
            {
              throw HTTP_EXCEPT (
                  HttpResponseCode::BAD_REQUEST,
                  "Center declination out of range [-90, 90] deg");
            }
          center.c[0] = std::fmod (center.c[0], 360.0);
          if (center.c[0] < 0.0)
            {
              center.c[0] += 360.0;
              if (center.c[0] == 360.0)
                {
                  center.c[0] = 0.0;
                }
            }
          sky[0] = center.c[0];
          sky[1] = center.c[1];
          wcs.skyToPixel (sky, center.c);
        }
      if (size.c[0] < 0.0 || size.c[1] < 0.0)
        {
          throw HTTP_EXCEPT (HttpResponseCode::BAD_REQUEST,
                             "Negative cutout size");
        }
      if (size.units != PIX)
        {
          switch (size.units)
            {
            case ARCSEC:
              size.c[0] *= RAD_PER_ARCSEC;
              size.c[1] *= RAD_PER_ARCSEC;
              break;
            case ARCMIN:
              size.c[0] *= RAD_PER_ARCMIN;
              size.c[1] *= RAD_PER_ARCMIN;
              break;
            case DEG:
              size.c[0] *= RAD_PER_DEG;
              size.c[1] *= RAD_PER_DEG;
              break;
            default:
              break;
            }
          xmin = search (wcs, sky, center.c, size.c[0] * 0.5, 0, -1);
          xmax = search (wcs, sky, center.c, size.c[0] * 0.5, 0, +1);
          ymin = search (wcs, sky, center.c, size.c[1] * 0.5, 1, -1);
          ymax = search (wcs, sky, center.c, size.c[1] * 0.5, 1, +1);
        }
      else
        {
          xmin = pixcen (center.c[0] - size.c[0] * 0.5);
          xmax = pixcen (center.c[0] + size.c[0] * 0.5);
          ymin = pixcen (center.c[1] - size.c[1] * 0.5);
          ymax = pixcen (center.c[1] + size.c[1] * 0.5);
        }
    }
  else
    {
      xmin = pixcen (center.c[0] - size.c[0] * 0.5);
      xmax = pixcen (center.c[0] + size.c[0] * 0.5);
      ymin = pixcen (center.c[1] - size.c[1] * 0.5);
      ymax = pixcen (center.c[1] + size.c[1] * 0.5);
    }

  // make sure sub-image overlaps image
  if (xmin > naxis[0] || ymin > naxis[1] || xmax < 1 || ymax < 1)
    {
      return false;
    }

  // store pixel-space cutout bounds in box
  box[0] = static_cast<long> (std::max (1.0, xmin));
  box[1] = static_cast<long> (std::max (1.0, ymin));
  box[2] = static_cast<long> (std::min (static_cast<double> (naxis[0]), xmax));
  box[3] = static_cast<long> (std::min (static_cast<double> (naxis[1]), ymax));
  return true;
}

// Regular expressions for recognizing various units.
boost::regex const _pixRe ("^(px?|pix(?:els?)?)\\s*$");
boost::regex const _arcsecRe ("^(\"|a(rc)?-?sec(onds?)?)\\s*$");
boost::regex const _arcminRe ("^('|a(rc)?-?min(utes?)?)\\s*$");
boost::regex const _degRe ("^(d(?:eg(?:rees?)?)?)\\s*$");
boost::regex const _radRe ("^rad(ians?)?\\s*$");

} // unnamed namespace

#define PP_MSG                                                                \
  format (                                                                    \
      "Value of %s parameter must consist of %s comma separated floating "    \
      "point numbers, followed by an optional units specification.",          \
      key.c_str (), requirePair ? "2" : "1 or 2")

Coords const
parseCoords (Environment const &env, string const &key, Units defaultUnits,
             bool requirePair)
{
  Coords coords;
  char *s = 0;

  string const value = env.getValue (key);
  string::size_type comma = value.find (',');
  if (comma == string::npos && requirePair)
    {
      throw HTTP_EXCEPT (HttpResponseCode::BAD_REQUEST, PP_MSG);
    }
  // get value of first coordinate
  coords.c[0] = std::strtod (value.c_str (), &s);
  if (s == 0 || s == value.c_str ())
    {
      throw HTTP_EXCEPT (HttpResponseCode::BAD_REQUEST, PP_MSG);
    }
  if (requirePair || comma != string::npos)
    {
      // get value of second coordinate
      for (; std::isspace (*s); ++s)
        {
        }
      if (static_cast<string::size_type> (s - value.c_str ()) != comma)
        {
          throw HTTP_EXCEPT (HttpResponseCode::BAD_REQUEST, PP_MSG);
        }
      coords.c[1] = std::strtod (value.c_str () + (comma + 1), &s);
      if (s == 0 || s == value.c_str () + (comma + 1))
        {
          throw HTTP_EXCEPT (HttpResponseCode::BAD_REQUEST, PP_MSG);
        }
    }
  else
    {
      // single coordinate value passed in
      coords.c[1] = coords.c[0];
    }
  coords.units = defaultUnits;
  for (; std::isspace (*s); ++s)
    {
    }
  if (*s != 0)
    {
      // parse unit specification
      if (boost::regex_match (s, _pixRe))
        {
          coords.units = PIX;
        }
      else if (boost::regex_match (s, _arcsecRe))
        {
          coords.units = ARCSEC;
        }
      else if (boost::regex_match (s, _arcminRe))
        {
          coords.units = ARCMIN;
        }
      else if (boost::regex_match (s, _degRe))
        {
          coords.units = DEG;
        }
      else if (boost::regex_match (s, _radRe))
        {
          coords.units = RAD;
        }
      else
        {
          throw HTTP_EXCEPT (
              HttpResponseCode::BAD_REQUEST,
              format ("Value of %s parameter has invalid trailing unit "
                      "specification",
                      key.c_str ()));
        }
    }
  return coords;
}

#undef PP_MSG

// == Wcs implementation ----

Wcs::Wcs (char *hdr, int nkeys) : _wcs (0), _nwcs (0)
{
  int nreject = 0;
  ::wcserr_enable (1);
  if (::wcspih (hdr, nkeys, WCSHDR_all, 0, &nreject, &_nwcs, &_wcs) != 0)
    {
      throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                         "Failed to extract WCS from FITS header");
    }
  if (_nwcs < 1)
    {
      ::wcsvfree (&_nwcs, &_wcs);
      throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                         "FITS file contains no valid WCSes");
    }
  // Remove PVi_ma distortion parameters if SIP distortion parameters
  // are also present. Some projects, like PTF, convert SCAMP/SWARP
  // distortion parameters to SIP. But SCAMP/SWARP's use of PVi_ma
  // conflicts with the FITS standard, and so those cards must be
  // removed to keep wcslib happy.
  //
  // See https://github.com/astropy/astropy/issues/299 for the gory
  // details.
  if (_wcs->npv != 0)
    {
      bool strip = true;
      for (int i = 0; i < _wcs->naxis; ++i)
        {
          if (!boost::algorithm::ends_with (_wcs->ctype[i], "-SIP"))
            {
              strip = false;
              break;
            }
        }
      if (strip)
        {
          for (int m = 0; m < _wcs->npv; ++m)
            {
              _wcs->pv[m].i = 0;
              _wcs->pv[m].m = 0;
              _wcs->pv[m].value = 0.0;
            }
          _wcs->npv = 0;
        }
    }
  if (::wcsset (_wcs) != 0)
    {
      std::string msg (_wcs->err != NULL ? _wcs->err->msg : "");
      ::wcsvfree (&_nwcs, &_wcs);
      throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR, msg);
    }
}

Wcs::~Wcs ()
{
  if (_wcs != 0)
    {
      ::wcsvfree (&_nwcs, &_wcs);
      _wcs = 0;
      _nwcs = 0;
    }
}

void
Wcs::pixelToSky (const double *pix, double *world)
{
  double imgcrd[2], phi[1], theta[1];
  int stat;
  int ret = ::wcsp2s (_wcs, 1, 2, pix, imgcrd, phi, theta, world, &stat);
  if (ret == 9)
    {
      throw HTTP_EXCEPT (HttpResponseCode::BAD_REQUEST,
                         "Invalid pixel coordinates");
    }
  else if (ret != 0)
    {
      throw HTTP_EXCEPT (
          HttpResponseCode::INTERNAL_SERVER_ERROR,
          "Failed to convert pixel coordinates to sky coordinates");
    }
  if (_wcs->lng != 0)
    {
      std::swap (world[0], world[1]);
    }
}

void
Wcs::skyToPixel (const double *sky, double *pix)
{
  double imgcrd[2], phi[1], theta[1], world[2];
  int stat, ret;
  world[_wcs->lng] = sky[0];
  world[_wcs->lat] = sky[1];
  ret = ::wcss2p (_wcs, 1, 2, world, imgcrd, phi, theta, pix, &stat);
  if (ret == 9)
    {
      throw HTTP_EXCEPT (HttpResponseCode::BAD_REQUEST,
                         "Invalid sky coordinates");
    }
  else if (ret != 0)
    {
      throw HTTP_EXCEPT (
          HttpResponseCode::INTERNAL_SERVER_ERROR,
          "Failed to convert sky coordinates to pixel coordinates");
    }
}

// == FitsFile implementation ----

FitsFile::FitsFile (char const *path) : _file (0)
{
  int status = 0;
  fits_open_file (&_file, path, READONLY, &status);
  checkFitsError (status);
}

FitsFile::~FitsFile ()
{
  if (_file != 0)
    {
      int status = 0;
      fits_close_file (_file, &status);
      _file = 0;
    }
}

void
streamSubimage (boost::filesystem::path const &path, Coords const &center,
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
          writer.write (reinterpret_cast<unsigned char *> (card), 80u);
          numBytes += 80;
        }
      if ((numBytes % 2880) != 0)
        {
          // pad header with spaces till its size is a multiple of 2880.
          size_t nb = 2880 - (numBytes % 2880);
          std::memset (padding, static_cast<int> (' '), nb);
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
      size_t bufsz = static_cast<size_t> (rowsz) * std::abs (bitpix) / 8;
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
                                 static_cast<unsigned char *> (buf.get ()),
                                 &anynul, &status);
              checkFitsError (status);
              break;
            case 16:
              fits_read_img_sht (f, 0, firstpix, rowsz, 0,
                                 static_cast<short *> (buf.get ()), &anynul,
                                 &status);
              checkFitsError (status);
#if __BYTE_ORDER == __LITTLE_ENDIAN
              {
                uint16_t *b = static_cast<uint16_t *> (buf.get ());
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
                                 static_cast<int *> (buf.get ()), &anynul,
                                 &status);
              checkFitsError (status);
#if __BYTE_ORDER == __LITTLE_ENDIAN
              {
                int32_t *b = static_cast<int32_t *> (buf.get ());
                for (long j = 0; j < rowsz; ++j)
                  {
                    b[j] = __builtin_bswap32 (b[j]);
                  }
              }
#endif
              break;
            case -32:
              fits_read_img_flt (f, 0, firstpix, rowsz, 0.0,
                                 static_cast<float *> (buf.get ()), &anynul,
                                 &status);
              checkFitsError (status);
#if __BYTE_ORDER == __LITTLE_ENDIAN
              {
                int32_t *b = static_cast<int32_t *> (buf.get ());
                for (long j = 0; j < rowsz; ++j)
                  {
                    b[j] = __builtin_bswap32 (b[j]);
                  }
              }
#endif
              break;
            case 64:
              fits_read_img_lnglng (f, 0, firstpix, rowsz, 0,
                                    static_cast<LONGLONG *> (buf.get ()),
                                    &anynul, &status);
              checkFitsError (status);
#if __BYTE_ORDER == __LITTLE_ENDIAN
              {
                int64_t *b = static_cast<int64_t *> (buf.get ());
                for (long j = 0; j < rowsz; ++j)
                  {
                    b[j] = __builtin_bswap64 (b[j]);
                  }
              }
#endif
              break;
            case -64:
              fits_read_img_dbl (f, 0, firstpix, rowsz, 0.0,
                                 static_cast<double *> (buf.get ()), &anynul,
                                 &status);
              checkFitsError (status);
#if __BYTE_ORDER == __LITTLE_ENDIAN
              {
                int64_t *b = static_cast<int64_t *> (buf.get ());
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
          writer.write (static_cast<unsigned char *> (buf.get ()), bufsz);
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

} // namespace ibe
