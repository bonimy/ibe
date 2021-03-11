#include "fits/FitsFile.hxx"

// Local headers
#include "fits/FitsError.hxx"
#include "fits/HDU.hxx"
#include "fits/HDUIterator.hxx"

namespace fits {
void FitsFile::deleter::operator()(pointer fptr) {
    int status = 0;
    fits_close_file(fptr, &status);
}

FitsFile::FitsFile(fitsfile* fptr) : fptr_(fptr, deleter()) {}

FitsFile::FitsFile(const std::string& path, FileMode mode)
        : FitsFile(open_fits_file(path, mode)) {}

FitsFile::FitsFile(void*& buffer, size_t& size, size_t delta_size, mem_realloc realloc)
        : FitsFile(open_mem_fitsfile(buffer, size, delta_size, realloc)) {}

bool FitsFile::operator==(const FitsFile& other) const { return fptr_ == other.fptr_; }
bool FitsFile::operator!=(const FitsFile& other) const { return !(*this == other); }

fitsfile* FitsFile::operator&() { return fptr_.get(); }
const fitsfile* FitsFile::operator&() const { return fptr_.get(); }

fitsfile& FitsFile::operator*() { return fptr_.operator*(); }
const fitsfile& FitsFile::operator*() const { return fptr_.operator*(); }

fitsfile& FitsFile::operator->() { return fptr_.operator*(); }
const fitsfile& FitsFile::operator->() const { return fptr_.operator*(); }

size_t FitsFile::hdu_count() {
    int status = 0;
    int result;
    if (fits_get_num_hdus(this->operator&(), &result, &status) > 0)
        throw FitsError(status);
    return static_cast<size_t>(result);
}
size_t FitsFile::current_hdu_num() {
    int result;
    fits_get_hdu_num(this->operator&(), &result);
    return static_cast<size_t>(result);
}

FitsFile::iterator FitsFile::begin() { return HDUIterator(*this, 1); }
FitsFile::iterator FitsFile::end() { return HDUIterator(*this, hdu_count() + 1); }

HDU FitsFile::make_hdu_current(size_t hdu_num) {
    int status = 0;
    int ext_type = 0;
    if (fits_movabs_hdu(fptr_.get(), static_cast<int>(hdu_num), &ext_type, &status) >
        0) {
        throw FitsError(status);
    }
    return HDU(*this, hdu_num);
}

HDU FitsFile::next_hdu() { return make_hdu_current(current_hdu_num() + 1); }

HDU FitsFile::create_image_hdu(PixelFormat bit_pix, std::vector<long>& naxes) {
    int status = 0;
    if (fits_create_img(fptr_.get(), static_cast<int>(bit_pix),
                        static_cast<int>(naxes.size()), naxes.data(), &status) > 0) {
        throw FitsError(status);
    }
    return HDU(*this, hdu_count() + 1);
}

void FitsFile::copy_hdu(HDU& hdu) {
    hdu.make_current();

    int status = 0;
    if (fits_copy_hdu(&hdu.owner_, fptr_.get(), 0, &status) > 0) {
        throw FitsError(status);
    }
}

void FitsFile::swap(FitsFile& other) { return std::swap(fptr_, other.fptr_); }

fitsfile* FitsFile::open_fits_file(const std::string& path, FileMode mode) {
    fitsfile* result;
    int status = 0;
    if (fits_open_file(&result, path.c_str(), static_cast<int>(mode), &status) > 0)
        throw FitsError(status);
    return result;
}
fitsfile* FitsFile::open_mem_fitsfile(void*& buffer, size_t& size, size_t delta_size,
                                      mem_realloc realloc) {
    fitsfile* result;
    int status = 0;
    if (fits_create_memfile(&result, &buffer, &size, delta_size, realloc, &status) > 0)
        throw FitsError(status);
    return result;
}

void swap(FitsFile& left, FitsFile& right) { return left.swap(right); }
}  // namespace fits
