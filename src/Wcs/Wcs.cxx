#include "../Wcs.hxx"
#include "../Cgi.hxx"

#include <boost/algorithm/string/predicate.hpp>

namespace ibe
{
Wcs::Wcs (char *fits_header)
{
  _wcs = wcsinit (fits_header);
  if (_wcs == nullptr)
    {
      throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                         "Failed to extract WCS from FITS header");
    }
  wcsoutinit (_wcs, const_cast<char*>("ICRS"));
}
}
