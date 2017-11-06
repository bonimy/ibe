#include "RAD_PER_DEG.hxx"
#include "pixcen.hxx"
#include "../../Cgi.hxx"
#include "../../Wcs.hxx"
#include "../../Coords.hxx"

#include <iostream>

namespace ibe
{
double const DEG_PER_RAD = 57.2957795130823208767981548141;
double const RAD_PER_ARCMIN = 0.000290888208665721596153948461415;
double const RAD_PER_ARCSEC = 0.00000484813681109535993589914102357;

double search (Wcs &wcs, const double sky[2], const double pix[2],
               const double size, const int dim, const int dir);

// Map the given center and size to a pixel-space box for a cutout. If the
// requested cutout doesn't overlap the image, \c false is returned. Results
// are
// stored in \c box as follows: box[0] = xmin, box[1] = ymin, box[2] = xmax,
// box[3] = ymax.
bool
cutoutPixelBox (Coords center, // Cutout center.
                Coords size,   // Cutout size.
                char *hdr,     // FITS header string (as returned by CFITSIO).
                long const *naxis, // Image dimensions (NAXIS1 and  NAXIS2).
                long *box) // Pixel-space cutout box; must point to an array of
                           // at least 4 longs.
{
  double xmin, xmax, ymin, ymax;
  if (center.units != PIX || size.units != PIX)
    {
      // need to map center and/or size to pixel coordinates
      Wcs wcs (hdr);
      double sky[2];
      if (center.units == PIX)
        {
          wcs.pixel_to_sky (center.c, sky);
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
          wcs.sky_to_pixel (sky, center.c);
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
  box[0] = static_cast<long>(std::max (1.0, xmin));
  box[1] = static_cast<long>(std::max (1.0, ymin));
  box[2] = static_cast<long>(std::min (static_cast<double>(naxis[0]), xmax));
  box[3] = static_cast<long>(std::min (static_cast<double>(naxis[1]), ymax));
  return true;
}
}
