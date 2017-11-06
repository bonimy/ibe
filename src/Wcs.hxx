#pragma once

#include <wcstools/wcs.h>

namespace ibe
{
/// RAII wrapper for the wcsprm struct from wcslib.
class Wcs
{
public:
  Wcs (char *fits_header);
  ~Wcs ();

  void pixel_to_sky (const double *pix, double *sky);
  void sky_to_pixel (const double *sky, double *pix);

private:
  // disable copy construction/assignment
  Wcs (Wcs const &) = delete;
  Wcs &operator=(Wcs const &);

  struct WorldCoor *_wcs = nullptr;
};
}
