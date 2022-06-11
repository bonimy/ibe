#include "check_fits_error.hxx"

// Local headers
#include "HttpException.hxx"
#include "HttpResponseCode.hxx"
#include "format.hxx"

// External APIs
#include <fitsio.h>

namespace ibe {

// Check if CFITSIO has failed and throw an internal server error if so.
void check_fits_error(int status) {
    char stat_msg[32];
    char err_msg[96];
    if (status != 0) {
        fits_get_errstatus(status, stat_msg);
        if (fits_read_errmsg(err_msg) != 0) {
            throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                              format("%s : %s", stat_msg, err_msg));
        }
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR, stat_msg);
    }
}
}  // namespace ibe
