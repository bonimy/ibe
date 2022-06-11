#pragma once

// Local headers
#include "PixelFormat.hxx"

// External APIs
#include <fitsio.h>

// Standard library
#include <memory>
#include <string>
#include <vector>

namespace fits {
enum class FileMode { read_only = READONLY, read_write = READWRITE };

typedef void* (*mem_realloc)(void* ptr, size_t new_size);

class HDU;
class HDUIterator;

class FitsFile {
public:
    struct deleter {
        using element_type = fitsfile;
        using pointer = fitsfile*;

        void operator()(pointer fptr);
    };

    using iterator = HDUIterator;

private:
    FitsFile(fitsfile* fptr);

public:
    // Read a FITS file from disk and optionally permit write operations.
    FitsFile(const std::string& path, FileMode mode = FileMode::read_only);

    // Construct a new FITS file and store in memory.
    FitsFile(void*& buffer, size_t& size, size_t delta_size = 0,
             mem_realloc realloc = nullptr);

    bool operator==(const FitsFile& other) const;
    bool operator!=(const FitsFile& other) const;

    fitsfile* get();
    const fitsfile* get() const;

    fitsfile& operator*();
    const fitsfile& operator*() const;

    fitsfile& operator->();
    const fitsfile& operator->() const;

    size_t hdu_count();
    size_t current_hdu_num();

    iterator begin();
    iterator end();

    HDU make_hdu_current(size_t hdu_num);

    HDU next_hdu();

    HDU create_image_hdu(PixelFormat pixel_format, std::vector<long>& naxes);

    void copy_hdu(HDU& hdu);

    void swap(FitsFile& other);

private:
    static fitsfile* open_fits_file(const std::string& path, FileMode mode);
    static fitsfile* open_mem_fitsfile(void*& buffer, size_t& size, size_t delta_size,
                                       mem_realloc realloc);

    std::shared_ptr<fitsfile> fptr_;

    friend class HDU;
};
}  // namespace fits
