#include "Wcs.hxx"

#include "HttpException.hxx"

namespace ibe {
Wcs::Wcs(char* fits_header) {
    wcs_ = wcsinit(fits_header);
    if (wcs_ == nullptr) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "Failed to extract WCS from FITS header");
    }
    wcsoutinit(wcs_, const_cast<char*>("ICRS"));
}

Wcs::~Wcs() {
    if (wcs_ != 0) {
        wcsfree(wcs_);
    }
}

void Wcs::pixel_to_sky(const double* pix, double* world) {
    pix2wcs(wcs_, pix[0], pix[1], &(world[0]), &(world[1]));
}

void Wcs::sky_to_pixel(const double* sky, double* pix) {
    int off_scale;
    wcsc2pix(wcs_, sky[0], sky[1], const_cast<char*>("ICRS"), &(pix[0]), &(pix[1]),
             &off_scale);

    if (off_scale == 1) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "Failed to convert sky coordinates to pixel coordinates");
    }
}
}  // namespace ibe
