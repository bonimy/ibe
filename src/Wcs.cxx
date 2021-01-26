#include "Wcs.hxx"

#include "Cgi.hxx"

namespace ibe {
Wcs::Wcs(char* fits_header) {
    _wcs = wcsinit(fits_header);
    if (_wcs == nullptr) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "Failed to extract WCS from FITS header");
    }
    wcsoutinit(_wcs, const_cast<char*>("ICRS"));
}

Wcs::~Wcs() {
    if (_wcs != 0) {
        wcsfree(_wcs);
    }
}

void Wcs::pixel_to_sky(const double* pix, double* world) {
    pix2wcs(_wcs, pix[0], pix[1], &(world[0]), &(world[1]));
}

void Wcs::sky_to_pixel(const double* sky, double* pix) {
    int off_scale;
    wcsc2pix(_wcs, sky[0], sky[1], const_cast<char*>("ICRS"), &(pix[0]), &(pix[1]),
             &off_scale);

    if (off_scale == 1) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "Failed to convert sky coordinates to pixel coordinates");
    }
}
}  // namespace ibe
