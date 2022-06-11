#pragma once

// Local headers
#include "FitsException.hxx"

// Standard library
#include <string>

namespace fits {

// A specialization of `FitsException` for errors that occur during cfitsio operations.
class FitsError : public FitsException {
public:
    FitsError(int status);
    FitsError(const std::string& message, int status);

    int status() const;

    // Gets the error type of the given status and flushes the cfitsio error message
    // queue to the resulting string.
    static std::string get_error_message(int status);

private:
    int status_;
};
}  // namespace fits
