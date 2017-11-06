#include "../Wcs.hxx"

namespace ibe
{
Wcs::~Wcs ()
{
  if (_wcs != 0)
    {
      wcsfree (_wcs);
    }
}
}
