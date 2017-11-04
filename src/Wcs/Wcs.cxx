#include "../Wcs.hxx"
#include "../Cgi.hxx"

#include <boost/algorithm/string/predicate.hpp>

namespace ibe
{
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
}
