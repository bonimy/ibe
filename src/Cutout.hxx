/** @file
 * @brief  Provides FITS image cutouts.
 * @author Serge Monkewitz
 */
#pragma once

#include "Coords.hxx"

#include "wcslib/wcs.h"
#include "wcslib/wcserr.h"
#include "wcslib/wcshdr.h"

#include "boost/filesystem.hpp"

#include "Cgi.hxx"

namespace ibe
{

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
  Wcs (Wcs const &) = delete;
  Wcs &operator=(Wcs const &);

  struct ::wcsprm *_wcs;
  int _nwcs;
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
