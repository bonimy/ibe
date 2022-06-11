#pragma once

// Standard library
#include <stdexcept>
#include <string>

namespace fits {

// A generic exception class for errors in fits library.
class FitsException : public std::runtime_error {
public:
    FitsException(const std::string& str);
};
}  // namespace fits
