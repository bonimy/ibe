#pragma once

// Standard library
#include <string>

// Local headers
#include "FitsException.hxx"

namespace fits {

// A specialization of `FitsException` for errors that occur during cfitsio operations.
class FitsError : public FitsException {
public:

    // Gets the error type of the given status and flushes the cfitsio error message
    // queue to the resulting string.
    static std::string get_error_message(int status);

    FitsError(int status);
    FitsError(const std::string& message, int status);

    int status() const;

private:
    int status_;
};
}  // namespace fits
