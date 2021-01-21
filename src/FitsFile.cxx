#include "FitsFile.hxx"

#include "checkFitsError.hxx"

namespace ibe {
FitsFile::FitsFile(char const* path) : _file(0) {
    int status = 0;
    fits_open_file(&_file, path, READONLY, &status);
    checkFitsError(status);
}

FitsFile::~FitsFile() {
    if (_file != 0) {
        int status = 0;
        fits_close_file(_file, &status);
        _file = 0;
    }
}
}  // namespace ibe
