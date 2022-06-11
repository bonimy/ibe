#pragma once

// Local headers
#include "fits/FitsFile.hxx"

// External APIs
#include <wcsxx/Rectangle.hxx>
#include <wcsxx/SpherePoint.hxx>
#include <wcsxx/Vector2d.hxx>
#include <wcsxx/Wcs.hxx>

namespace ibe {
long pixel_bounds(wcsxx::Wcs& wcs, const wcsxx::SpherePoint& center,
                  const wcsxx::Vector2d& pixel_direction, double radius);
wcsxx::Rectangle<long> pixel_bounds(wcsxx::Wcs& wcs, const wcsxx::SpherePoint& center,
                                    double radius);

void make_cutout(fits::FitsFile& source, fits::FitsFile& dest,
                 wcsxx::SpherePoint center, double radius);
void make_cutout(fits::HDU& source, fits::FitsFile& dest, wcsxx::SpherePoint center,
                 double radius);
}  // namespace ibe
