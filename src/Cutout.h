/** @file
  * @brief  Provides FITS image cutouts.
  * @author Serge Monkewitz
  */
#ifndef CUTOUT_H_
#define CUTOUT_H_

#include <string>
#include "fitsio.h"
extern "C" {
#include "fitsio2.h"
}
#include "wcslib/wcs.h"
#include "wcslib/wcshdr.h"

#include "boost/filesystem.hpp"

#include "Cgi.h"

namespace ibe
{

namespace
{
// unit conversion constants
double const DEG_PER_RAD = 57.2957795130823208767981548141;
double const RAD_PER_DEG = 0.0174532925199432957692369076849;
double const RAD_PER_ARCMIN = 0.000290888208665721596153948461415;
double const RAD_PER_ARCSEC = 0.00000484813681109535993589914102357;
}

/** Units that must to be dealt with.
  */
enum Units
{
  PIX = 0,
  ARCSEC,
  ARCMIN,
  DEG,
  RAD
};

/** A coordinate pair.
  */
struct Coords
{
  double c[2];
  Units units;
};

/** Parse a string representation of a coordinate pair with an
  * optional unit specification.
  */
Coords const parseCoords (Environment const &env, std::string const &key,
                          Units defaultUnits, bool requirePair);

/** RAII wrapper for the wcsprm struct from wcslib.
  */
class Wcs
{
public:
  Wcs (char *hdr, int nkeys);
  ~Wcs ();

  void pixelToSky (const double *pix, double *sky);
  void skyToPixel (const double *sky, double *pix);

private:
  // disable copy construction/assignment
  Wcs (Wcs const &);
  Wcs &operator=(Wcs const &);

  struct ::wcsprm *_wcs;
  int _nwcs;
};

/** RAII wrapper for a ::fitsfile pointer.
  */
class FitsFile
{
public:
  FitsFile (char const *path);
  ~FitsFile ();

  // conversion operators
  operator ::fitsfile *() { return _file; }
  operator ::fitsfile const *() { return _file; }

private:
  FitsFile (FitsFile const &);
  FitsFile &operator=(FitsFile const &);

  ::fitsfile *_file;
};

/** Stream a FITS image cutout to a Writer.
  */
void streamSubimage (
    boost::filesystem::path const &path, ///< \param[in] Path to FITS file.
    Coords const &center,                ///< \param[in] Cutout center.
    Coords const &size,                  ///< \param[in] Cutout size.
    Writer &writer                       ///< \param[inout] Output writer.
    );

} // namespace ibe

#endif // CUTOUT_H_
