#pragma once

#include <wcslib/wcs.h>
#include <wcslib/wcserr.h>
#include <wcslib/wcshdr.h>

namespace ibe
{
/// RAII wrapper for the wcsprm struct from wcslib.
class Wcs
{
public:
  Wcs (char *hdr, int nkeys);
  ~Wcs ();

  void pixelToSky (const double *pix, double *sky);
  void skyToPixel (const double *sky, double *pix);

private:
  // disable copy construction/assignment
  Wcs (Wcs const &) = delete;
  Wcs &operator=(Wcs const &);

  struct ::wcsprm *_wcs;
  int _nwcs;
};

}
