#include "FitsException.hxx"

namespace fits {
FitsException::FitsException(const std::string& str)
        : std::runtime_error(str.c_str()) {}
}  // namespace fits
