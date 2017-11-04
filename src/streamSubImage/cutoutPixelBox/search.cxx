#include "RAD_PER_DEG.hxx"
#include "pixcen.hxx"
#include "../../Wcs.hxx"

namespace ibe
{
// Return the angular separation in radians between 2 vectors in R3.
inline double
dist (const double *v1, const double *v2)
{
  double cs = v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2];
  double x = v1[1] * v2[2] - v1[2] * v2[1];
  double y = v1[2] * v2[0] - v1[0] * v2[2];
  double z = v1[0] * v2[1] - v1[1] * v2[0];
  double ss = sqrt (x * x + y * y + z * z);
  return ((ss != 0.0) || (cs != 0.0)) ? std::atan2 (ss, cs) : 0.0;
}

// Convert spherical coordinates (deg) to a vector in R3.
inline void s2c (const double *sky, double *v)
{
  v[0] = std::cos (RAD_PER_DEG * sky[0]) * std::cos (RAD_PER_DEG * sky[1]);
  v[1] = std::sin (RAD_PER_DEG * sky[0]) * std::cos (RAD_PER_DEG * sky[1]);
  v[2] = std::sin (RAD_PER_DEG * sky[1]);
}

// Return the closest x or y coordinate separated by at least size radians from
// the given center in the given direction.
double search (Wcs &wcs,            // WCS for 2D image to search
               const double sky[2], // center to search outwards from
               const double pix[2], // pixel coordinates of sky
               const double size,   // desired size in radians
               const int dim,       // axis to search along: 0 (x) or 1 (y)
               const int dir)       // direction to search along: +1 or -1
{
  double cen[3], v[3], p[2], s[2], d, inc, scale;
  s2c (sky, cen);
  inc = dir;
  p[!dim] = pix[!dim];
  p[dim] = pixcen (pix[dim]) + 0.5 * inc;
  scale = 2.0;
  while (std::fabs (inc) >= 1.0 && !std::isinf (p[0]) && !std::isinf (p[1]))
    {
      wcs.pixelToSky (p, s);
      s2c (s, v);
      d = dist (cen, v);
      if (d < size)
        {
          inc *= scale;
          p[dim] += inc;
        }
      else if (d > size)
        {
          scale = 0.5;
          inc *= 0.5;
          p[dim] -= inc;
        }
      else
        {
          break;
        }
    }
  return pixcen (p[dim]);
}
}
