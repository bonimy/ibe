#pragma once

// Local headers
#include "Coords.hxx"
#include "Writer.hxx"
#include "ibe_filesystem.hxx"

namespace ibe {
void stream_subimage(fs::path const& path, Coords const& center, Coords const& size,
                     Writer& writer);
}
