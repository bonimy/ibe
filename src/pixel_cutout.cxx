#include "pixel_cutout.hxx"

// Local headers
#include "fits/FitsError.hxx"
#include "fits/FitsFile.hxx"
#include "fits/HDUIterator.hxx"

// External APIs
#include <wcsxx/Rectangle.hxx>
#include <wcsxx/SpherePoint.hxx>
#include <wcsxx/Vector2d.hxx>
#include <wcsxx/Wcs.hxx>
#include <wcsxx/WcsError.hxx>

// Standard library
#include <algorithm>
#include <cstdlib>
#include <functional>
#include <memory>
#include <numeric>
#include <unordered_set>
#include <vector>

using namespace wcsxx;
using namespace fits;

namespace ibe {
long pixel_bounds(Wcs& wcs, const SpherePoint& center, const Vector2d& pixel_direction,
                  double radius) {
    // The scaling parameter determines how we grow or shrink our step distance until we
    // fall onto our pixel boundary. We will either double our distance (scale = 2.0)
    // until we exceed the search radius, or halve it (scale = 0.5) once we exceed it.
    double scale = 2.0;

    // The direction from the center we are traveling.
    auto pixel_unit_direction = pixel_direction.unit_vector();

    // The absolute pixel coordinate of the celestial center coordinate (radians).
    Vector2d pixel_center = wcs.sky_to_pixel<SpherePoint, Vector2d>(center, true);

    // The absolute pixel coordinate of our search position. We initialize it to be a
    // half pixel away from the center, going in the given direction.
    Vector2d pixel_pos = pixel_center + (pixel_unit_direction / 2);

    // Determines how many pixels we march toward `pixel_unit_direction` (or away from
    // when we are shrinking our search radius).
    double step = 1.0;

    // Continue refining search until we are within one pixel of tolerance. Because we
    // are dealing with exponential growth, we track that `step` remains finite.
    while (step >= 1.0 && !std::isinf(step)) {
        // Celestial coordinate (radians) of `pixel_pos`.
        SpherePoint sky_offset =
                wcs.pixel_to_sky<Vector2d, SpherePoint>(pixel_pos, true);

        // Get angular distance between `sky_offset` and `center`.
        double distance = sky_offset.angular_distance_to(center);

        // Determine whether we grow or shrink or step distance based on whether we are
        // inside or outside of the search radius.
        if (distance < radius) {
            // If we're inside the search radius, then double our step distance to try
            // to get us outside of the radius even faster.
            //
            // It is also possible that `scale == 0.5` once we've exceeded the radius,
            // then fall back inside while backtracking. In this case, the step distance
            // will be halved as we approach the radius.
            step *= scale;

            // Update `pixel_pos` to go forward by the next amount of distance.
            pixel_pos += pixel_unit_direction * step;
        } else if (distance > radius) {
            // If we are instead now outside of the radius, the we need to start
            // gradually
            // refining our distance until we are within one pixel of radius.
            scale = 0.5;

            // Shrink the step distance by half.
            step *= scale;

            // Update `pixel_pos` to go backward by the next amount of distance.
            pixel_pos -= pixel_unit_direction * step;
        } else {
            // If we somehow land exactly on the radius, then we're done!
            break;
        }
    }

    if (std::isinf(step)) {
        // TODO(nrg): Throw a better exception.
        throw std::range_error("Could not find boundary.");
    }

    // We convert from double to long since we are seeking a discrete pixel coordinate.
    return std::lround(std::abs(Vector2d::dot(pixel_pos, pixel_direction)));
}

Rectangle<long> pixel_bounds(Wcs& wcs, const SpherePoint& center, double radius) {
    return Rectangle<long>(pixel_bounds(wcs, center, Vector2d(-1, 0), radius),
                           pixel_bounds(wcs, center, Vector2d(0, -1), radius),
                           pixel_bounds(wcs, center, Vector2d(+1, 0), radius),
                           pixel_bounds(wcs, center, Vector2d(0, +1), radius));
}

void make_cutout(FitsFile& source, FitsFile& dest, SpherePoint center, double radius) {
    for (HDU hdu : source) {
        make_cutout(hdu, dest, center, radius);
    }
}

void make_cutout(fits::HDU& source_hdu, fits::FitsFile& dest, wcsxx::SpherePoint center,
                 double radius) {
    // Get HDU axes.
    std::vector<long> source_naxes = source_hdu.naxes();

    // Do pure HDU copies for non-images or images with zero size.
    if (source_hdu.ext_type() != HDU::Type::image || source_naxes.size() < 2 ||
        std::any_of(source_naxes.begin(), source_naxes.end(),
                    [](long naxis) { return naxis == 0; })) {
        dest.copy_hdu(source_hdu);
    }

    // Initialize celestial wcs for current HDU.
    Wcs wcs(2);
    try {
        source_hdu.make_current();
        wcs = Wcs::create_from_fits_file(*source_hdu.owner())[0].create_sky_wcs();
        wcs.fix_units(true);
        wcs.setup();
    } catch (WcsError) {
        // Do not make cutouts of images with no celestial axes.
        dest.copy_hdu(source_hdu);
        return;
    }

    // Calculate cutout bounds for image.
    Rectangle<long> bounds = pixel_bounds(wcs, center, radius);

    // Get naxes for new bounds.
    std::vector<long> dest_naxes = source_naxes;
    dest_naxes[wcs->lat] = bounds.width() + 1;
    dest_naxes[wcs->lng] = bounds.height() + 1;

    // Get pixel center for cutout HDU.
    Vector2d top_left = Vector2d(static_cast<double>(bounds.left) - 1,
                                 static_cast<double>(bounds.top) - 1);
    Vector2d pixel_center = wcs.crpix() - top_left;

    // Get coordinate of first pixel for source subset.
    std::vector<long> first(dest_naxes.size(), 1);
    first[wcs->lat] = bounds.left + 1;
    first[wcs->lng] = bounds.bottom + 1;

    // Get coordinate of last pixel for source subset.
    std::vector<long> last(source_naxes);
    last[wcs->lat] = bounds.right + 1;
    last[wcs->lng] = bounds.top + 1;

    // Turn off scaling before reading image.
    source_hdu.clear_bscale();
    Buffer<void> buffer = source_hdu.read_image_subset(first, last);

    // Initialize cutout HDU.
    HDU dest_hdu = dest.create_image_hdu(source_hdu.pixel_format(), dest_naxes);

    // Store initial keywords of new HDU to not overwrite them.
    std::unordered_set<std::string> source_keys;
    for (Keyword keyword : dest_hdu.read_keys()) {
        // Do not add any initial comments or history strings.
        if (keyword.name == "COMMENT" || keyword.name == "HISTORY") {
            continue;
        }

        source_keys.insert(keyword.name);
    }

    // Get "CRPIXn" strings for latitude and longitude axes.
    value_str crpix_lat = "CRPIX" + std::to_string(wcs->lat + 1);
    value_str crpix_lng = "CRPIX" + std::to_string(wcs->lng + 1);

    // Write header to dest HDU.
    for (Keyword keyword : source_hdu.read_keys()) {
        // Do not add empty or preexisting strings.
        if (keyword.name.empty() ||
            source_keys.find(keyword.name) != source_keys.end()) {
            continue;
        }

        // Apply new "CRPIXn" values for latitude and longitude axes.
        if (keyword.name == crpix_lat) {
            dest_hdu.write_float(keyword.name, static_cast<float>(pixel_center.x),
                                 keyword.comment);
            continue;
        }
        if (keyword.name == crpix_lng) {
            dest_hdu.write_float(keyword.name, static_cast<float>(pixel_center.y),
                                 keyword.comment);
            continue;
        }

        if (dest_hdu.is_compressed_image() && keyword.name == "EXTNAME") {
            dest_hdu.write_card(
                    "EXTNAME = 'COMPRESSED_IMAGE'   / name of this binary table "
                    "extension");
            continue;
        }

        // Copy keyword to the new HDU.
        dest_hdu.write_key(keyword);
    }

    // Set first coordinate components for celestial axes to beginning of image.
    first[wcs->lat] = 1;
    first[wcs->lng] = 1;

    // Set last coordinate components for celestial axes to end of image.
    last[wcs->lat] = bounds.width() + 1;
    last[wcs->lng] = bounds.height() + 1;

    // Turn off scaling for writing.
    dest_hdu.set_bscale(1, 0);
    dest_hdu.write_image_subset(first, last, buffer);
}
}  // namespace ibe
