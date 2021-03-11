#include "FitsFile.hxx"

// Local headers
#include "check_fits_error.hxx"

namespace ibe {
FitsFile::FitsFile(char const* path) : file_(0) {
    int status = 0;
    fits_open_file(&file_, path, READONLY, &status);
    check_fits_error(status);
}

FitsFile::~FitsFile() {
    if (file_ != 0) {
        int status = 0;
        fits_close_file(file_, &status);
        file_ = 0;
    }
}
}  // namespace ibe
