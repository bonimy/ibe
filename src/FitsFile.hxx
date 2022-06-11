#pragma once

// External APIs
#include <fitsio.h>

// Standard library
#include <string>

namespace ibe {

/// RAII wrapper for a ::fitsfile pointer.
class FitsFile {
public:
    FitsFile(char const* path);
    ~FitsFile();

    // conversion operators
    operator ::fitsfile*() { return file_; }
    operator ::fitsfile const *() { return file_; }

private:
    FitsFile(FitsFile const&) = delete;
    FitsFile& operator=(FitsFile const&) = delete;

    ::fitsfile* file_;
};
}  // namespace ibe
