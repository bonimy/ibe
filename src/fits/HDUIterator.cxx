#include "fits/HDUIterator.hxx"

namespace fits {
HDUIterator::HDUIterator(const FitsFile& fits, size_t hdu_index)
        : fits_(fits), hdu_index_(hdu_index) {}

bool HDUIterator::operator==(const HDUIterator& right) const {
    return fits_ == right.fits_ && hdu_index_ == right.hdu_index_;
}

void HDUIterator::swap(HDUIterator& other) {
    std::swap(fits_, other.fits_);
    std::swap(hdu_index_, other.hdu_index_);
}

HDUIterator::reference HDUIterator::operator*() { return HDU(fits_, hdu_index_); }

HDUIterator& HDUIterator::operator++() {
    hdu_index_++;
    return *this;
}
HDUIterator HDUIterator::operator++(int) {
    HDUIterator result = *this;
    ++*this;
    return result;
}

HDUIterator& HDUIterator::operator--() {
    hdu_index_--;
    return *this;
}
HDUIterator HDUIterator::operator--(int) {
    HDUIterator result = *this;
    --*this;
    return result;
}

HDUIterator& HDUIterator::operator+=(difference_type n) {
    hdu_index_ += n;
    return *this;
}
HDUIterator HDUIterator::operator+(difference_type n) const {
    HDUIterator result = *this;
    return (result += n);
}

HDUIterator::difference_type HDUIterator::operator-(const HDUIterator& other) const {
    return hdu_index_ - other.hdu_index_;
}

HDUIterator::reference HDUIterator::operator[](difference_type n) {
    return HDU(fits_, hdu_index_ + n);
}

bool HDUIterator::operator<(const HDUIterator& other) const {
    return hdu_index_ < other.hdu_index_;
}
}  // namespace fits
