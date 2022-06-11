#include "FitsError.hxx"

// Local headers
#include "arstring.hxx"

// External APIs
#include <fitsio.h>

// Standard library
#include <sstream>

namespace fits {
FitsError::FitsError(int status) : FitsError(get_error_message(status), status) {}
FitsError::FitsError(const std::string& message, int status)
        : FitsException(message), status_(status) {}

int FitsError::status() const { return status_; }

std::string FitsError::get_error_message(int status) {
    using error_status_str = arstring<FLEN_STATUS>;
    using error_message_str = arstring<FLEN_ERRMSG>;

    std::stringstream ss;

    // Get short error message corresponding to given status.
    error_status_str msg;
    fits_get_errstatus(status, msg);
    ss << msg;

    // Flush error message stack to result string.
    error_message_str err;
    while (fits_read_errmsg(err) > 0) ss << std::endl << err;

    return ss.str();
}
}  // namespace fits
