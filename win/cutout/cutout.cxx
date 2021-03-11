// Standard library
#include <cstdio>
#include <iostream>

// Third-party headers
#include <ibe/fits/FitsError.hxx>
#include <ibe/fits/FitsFile.hxx>
#include <ibe/pixel_cutout.hxx>
#include <wcslibxx/SpherePoint.hxx>
#include <wcslibxx/WcsError.hxx>
#include <wcslibxx/math_utils.hxx>

int main() {
    size_t size = 0;
    void* buffer = nullptr;

    try {
        fits::FitsFile fits("TBHICUBE.FITS");
        fits::FitsFile dest(buffer, size, 0, std::realloc);

        constexpr wcsxx::SpherePoint center(wcsxx::degrees_to_radians(260),
                                            wcsxx::degrees_to_radians(60));
        constexpr double radius = wcsxx::degrees_to_radians(1.5);
        ibe::make_cutout(fits, dest, center, radius);
    } catch (fits::FitsException ex) {
        std::cout << ex.what() << std::endl;
        return 1;
    } catch (wcsxx::WcsError ex) {
        std::cout << ex.what() << std::endl;
        return 1;
    }

    std::fwrite(buffer, 1, size, stdout);

    return 0;
}
