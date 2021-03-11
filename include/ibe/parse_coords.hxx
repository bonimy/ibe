#pragma once

// Local headers
#include "Coords.hxx"
#include "Environment.hxx"
#include "Units.hxx"

namespace ibe {
Coords const parse_coords(Environment const& env, std::string const& key,
                          Units default_units, bool require_pair);
}
