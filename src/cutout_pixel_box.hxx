#pragma once

// Local headers
#include "Coords.hxx"

namespace ibe {
bool cutout_pixel_box(Coords center, Coords size, char* hdr, long const* naxis,
                      long* box);
}
