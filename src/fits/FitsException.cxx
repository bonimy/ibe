#include "fits/FitsException.hxx"

namespace fits {
FitsException::FitsException(const std::string& str) : std::exception(str.c_str()) {}
}  // namespace fits
