#pragma once

// Standard library
#include <exception>
#include <string>

namespace fits {

// A generic exception class for errors in fits library.
class FitsException : public std::exception {
public:
    FitsException(const std::string& str);
};
}  // namespace fits
