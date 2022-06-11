#pragma once

// Standard library
#include <string>

namespace ibe {
/** Returns a formatted string obtained by passing @c fmt and any trailing
 * arguments to the C @c vsnprintf function.
 */
std::string const format(char const* fmt, ...);
}  // namespace ibe
