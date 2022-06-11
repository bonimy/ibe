#pragma once

// Local headers
#include "FitsFile.hxx"
#include "HDU.hxx"

// Standard library
#include <iterator>

namespace fits {
class HDUIterator {
public:
    using iterator_category = std::input_iterator_tag;
    using value_type = HDU;
    using reference = value_type;
    using difference_type = std::ptrdiff_t;
    using pointer = void;

    HDUIterator(const FitsFile& fits, size_t hdu_index);

    bool operator==(const HDUIterator& right) const;
    bool operator!=(const HDUIterator& right) const { return !(*this == right); }

    void swap(HDUIterator& other);

    reference operator*();
    reference operator->() { return this->operator*(); }

    HDUIterator& operator++();
    HDUIterator operator++(int);

    HDUIterator& operator--();
    HDUIterator operator--(int);

    HDUIterator& operator+=(difference_type n);
    HDUIterator operator+(difference_type n) const;

    HDUIterator& operator-=(difference_type n) { return *this += -n; }
    HDUIterator operator-(difference_type n) const { return *this + -n; }

    difference_type operator-(const HDUIterator& other) const;

    reference operator[](difference_type n);

    bool operator<(const HDUIterator& other) const;
    bool operator>(const HDUIterator& other) const { return other < *this; }
    bool operator<=(const HDUIterator& other) const { return !(other < *this); }
    bool operator>=(const HDUIterator& other) const { return !(*this < other); }

private:
    FitsFile fits_;
    size_t hdu_index_;
};

HDUIterator operator+(HDUIterator::difference_type n, const HDUIterator& it);
}  // namespace fits
