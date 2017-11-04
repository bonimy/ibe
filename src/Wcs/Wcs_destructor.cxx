#include "../Wcs.hxx"

namespace ibe
{
Wcs::~Wcs ()
{
  if (_wcs != 0)
    {
      ::wcsvfree (&_nwcs, &_wcs);
      _wcs = 0;
      _nwcs = 0;
    }
}
}
