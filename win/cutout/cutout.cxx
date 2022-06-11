// External APIs
#include <ibe/fits/FitsError.hxx>
#include <ibe/fits/FitsFile.hxx>
#include <ibe/fits/HDU.hxx>
#include <ibe/fits/HDUIterator.hxx>
#include <ibe/pixel_cutout.hxx>
#include <wcsxx/SpherePoint.hxx>
#include <wcsxx/WcsError.hxx>
#include <wcsxx/math_utils.hxx>

// Standard library
#include <cstdio>
#include <iostream>

bool compare_key_list(const std::vector<fits::Keyword>& x,
                      const std::vector<fits::Keyword>& y) {
    if (x.size() != y.size()) return false;

    for (size_t i = 0; i < x.size(); i++) {
        if (x[i].name != y[i].name) {
            return false;
        }
    }
    return true;
}


int main() {
    fits::FitsFile ffile("33/SPECTRA_COMBINED.fits");
    auto count = ffile.hdu_count();
    std::vector<std::vector<fits::Keyword>> all_keys;
    for (fits::HDU hdu : ffile) {
        all_keys.push_back(hdu.read_keys());
    }

    for (size_t i = 2; i < all_keys.size(); i++) {
        if (!compare_key_list(all_keys[i - 1], all_keys[i])) {
            std::cout << "ASDFdsd" << std::endl;
        }
    }

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
