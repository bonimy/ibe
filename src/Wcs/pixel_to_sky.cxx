#include "../Cgi.hxx"
#include "../Wcs.hxx"

namespace ibe {
void Wcs::pixel_to_sky(const double* pix, double* world) {
    pix2wcs(_wcs, pix[0], pix[1], &(world[0]), &(world[1]));
}
}  // namespace ibe
