#pragma once

#include <cmath>

namespace ibe
{
// Return the center coordinate of the pixel containing x, FITS conventions.
// Pixel N has center coordinate N, and spans [N - 0.5, N + 0.5).
inline double pixcen (double x) { return std::floor (x + 0.5); }
}
