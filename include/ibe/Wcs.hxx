#pragma once

#if defined(WIN32) && !defined(__STDC__)
#define __WINDOWS_DOESNT_LIKE_STDC__
#define __STDC__
#endif

#include <libwcs/wcs.h>

#ifdef __WINDOWS_DOESNT_LIKE_STDC__
#undef __WINDOWS_DOESNT_LIKE_STDC__
#undef __STDC__
#endif

namespace ibe {

/// RAII wrapper for the wcsprm struct from wcslib.
class Wcs {
public:
    Wcs(char* fits_header);
    ~Wcs();

    void pixel_to_sky(const double* pix, double* sky);
    void sky_to_pixel(const double* sky, double* pix);

private:

    // disable copy construction/assignment
    Wcs(Wcs const&) = delete;
    Wcs& operator=(Wcs const&);

    struct WorldCoor* wcs_ = nullptr;
};
}  // namespace ibe
