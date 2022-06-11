#pragma once

// Standard library
#include <exception>
#include <ostream>

namespace ibe {
void write_error_response(std::ostream& stream, std::exception const& e);
void write_error_response(std::ostream& stream);
}  // namespace ibe
