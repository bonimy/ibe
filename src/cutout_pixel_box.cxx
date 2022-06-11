#include "cutout_pixel_box.hxx"

// Local headers
#include "HttpException.hxx"
#include "HttpResponseCode.hxx"
#include "Wcs.hxx"

// Standard library
#include <algorithm>
#include <cmath>

namespace ibe {
double const RAD_PER_DEG = 0.0174532925199432957692369076849;
double const DEG_PER_RAD = 57.2957795130823208767981548141;
double const RAD_PER_ARCMIN = 0.000290888208665721596153948461415;
double const RAD_PER_ARCSEC = 0.00000484813681109535993589914102357;

// Return the center coordinate of the pixel containing x, FITS conventions.
// Pixel N has center coordinate N, and spans [N - 0.5, N + 0.5).
inline double pixcen(double x) { return std::floor(x + 0.5); }

double search(Wcs& wcs, const double sky[2], const double pix[2], const double size,
              const int dim, const int dir);

// Map the given center and size to a pixel-space box for a cutout. If the
// requested cutout doesn't overlap the image, \c false is returned. Results
// are
// stored in \c box as follows: box[0] = xmin, box[1] = ymin, box[2] = xmax,
// box[3] = ymax.
bool cutout_pixel_box(Coords center,  // Cutout center.
                      Coords size,    // Cutout size.
                      char* hdr,      // FITS header string (as returned by CFITSIO).
                      long const* naxis,  // Image dimensions (NAXIS1 and  NAXIS2).
                      long* box)  // Pixel-space cutout box; must point to an array of

// at least 4 longs.
{
    double xmin, xmax, ymin, ymax;
    if (center.units != PIX || size.units != PIX) {
        // need to map center and/or size to pixel coordinates
        Wcs wcs(hdr);
        double sky[2];
        if (center.units == PIX) {
            wcs.pixel_to_sky(center.c, sky);
        } else {
            // convert to degrees
            switch (center.units) {
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
            if (center.c[1] < -90.0 || center.c[1] > 90.0) {
                throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                                  "Center declination out of range [-90, 90] deg");
            }
            center.c[0] = std::fmod(center.c[0], 360.0);
            if (center.c[0] < 0.0) {
                center.c[0] += 360.0;
                if (center.c[0] == 360.0) {
                    center.c[0] = 0.0;
                }
            }
            sky[0] = center.c[0];
            sky[1] = center.c[1];
            wcs.sky_to_pixel(sky, center.c);
        }
        if (size.c[0] < 0.0 || size.c[1] < 0.0) {
            throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST, "Negative cutout size");
        }
        if (size.units != PIX) {
            switch (size.units) {
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
            xmin = search(wcs, sky, center.c, size.c[0] * 0.5, 0, -1);
            xmax = search(wcs, sky, center.c, size.c[0] * 0.5, 0, +1);
            ymin = search(wcs, sky, center.c, size.c[1] * 0.5, 1, -1);
            ymax = search(wcs, sky, center.c, size.c[1] * 0.5, 1, +1);
        } else {
            xmin = pixcen(center.c[0] - size.c[0] * 0.5);
            xmax = pixcen(center.c[0] + size.c[0] * 0.5);
            ymin = pixcen(center.c[1] - size.c[1] * 0.5);
            ymax = pixcen(center.c[1] + size.c[1] * 0.5);
        }
    } else {
        xmin = pixcen(center.c[0] - size.c[0] * 0.5);
        xmax = pixcen(center.c[0] + size.c[0] * 0.5);
        ymin = pixcen(center.c[1] - size.c[1] * 0.5);
        ymax = pixcen(center.c[1] + size.c[1] * 0.5);
    }

    // make sure sub-image overlaps image
    if (xmin > naxis[0] || ymin > naxis[1] || xmax < 1 || ymax < 1) {
        return false;
    }

    // store pixel-space cutout bounds in box
    box[0] = static_cast<long>(std::max(1.0, xmin));
    box[1] = static_cast<long>(std::max(1.0, ymin));
    box[2] = static_cast<long>(std::min(static_cast<double>(naxis[0]), xmax));
    box[3] = static_cast<long>(std::min(static_cast<double>(naxis[1]), ymax));
    return true;
}

// Return the angular separation in radians between 2 vectors in R3.
inline double dist(const double* v1, const double* v2) {
    double cs = v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2];
    double x = v1[1] * v2[2] - v1[2] * v2[1];
    double y = v1[2] * v2[0] - v1[0] * v2[2];
    double z = v1[0] * v2[1] - v1[1] * v2[0];
    double ss = sqrt(x * x + y * y + z * z);
    return ((ss != 0.0) || (cs != 0.0)) ? std::atan2(ss, cs) : 0.0;
}

// Convert spherical coordinates (deg) to a vector in R3.
inline void s2c(const double* sky, double* v) {
    v[0] = std::cos(RAD_PER_DEG * sky[0]) * std::cos(RAD_PER_DEG * sky[1]);
    v[1] = std::sin(RAD_PER_DEG * sky[0]) * std::cos(RAD_PER_DEG * sky[1]);
    v[2] = std::sin(RAD_PER_DEG * sky[1]);
}

// Return the closest x or y coordinate separated by at least size radians from
// the given center in the given direction.
double search(Wcs& wcs,             // WCS for 2D image to search
              const double sky[2],  // center to search outwards from
              const double pix[2],  // pixel coordinates of sky
              const double size,    // desired size in radians
              const int dim,        // axis to search along: 0 (x) or 1 (y)
              const int dir)        // direction to search along: +1 or -1
{
    double cen[3], v[3], p[2], s[2], d, inc, scale;
    s2c(sky, cen);
    inc = dir;
    p[!dim] = pix[!dim];
    p[dim] = pixcen(pix[dim]) + 0.5 * inc;
    scale = 2.0;
    while (std::fabs(inc) >= 1.0 && !std::isinf(p[0]) && !std::isinf(p[1])) {
        wcs.pixel_to_sky(p, s);
        s2c(s, v);
        d = dist(cen, v);
        if (d < size) {
            inc *= scale;
            p[dim] += inc;
        } else if (d > size) {
            scale = 0.5;
            inc *= 0.5;
            p[dim] -= inc;
        } else {
            break;
        }
    }
    return pixcen(p[dim]);
}
}  // namespace ibe
