/** @file
 * @brief  FITS image cutout implementation.
 * @author Serge Monkewitz
 */
#include "../Coords.hxx"
#include "../Cgi.hxx"
#include "../Wcs.hxx"


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

}
