#pragma once

// Standard library
#include <iterator>

// Local headers
#include "FitsFile.hxx"
#include "HDU.hxx"

namespace fits {
class HDUIterator {
public:
    using iterator_category = std::input_iterator_tag;
    using value_type = HDU;
    using reference = value_type;
    using difference_type = size_t;
    using pointer = void;

    HDUIterator(const FitsFile& fits, size_t hdu_index);

    bool operator==(const HDUIterator& right) const;
    inline bool operator!=(const HDUIterator& right) const { return !(*this == right); }

    void swap(HDUIterator& other);

    reference operator*();
    inline reference operator->() { return this->operator*(); }

    HDUIterator& operator++();
    HDUIterator operator++(int);

    HDUIterator& operator--();
    HDUIterator operator--(int);

    HDUIterator& operator+=(difference_type n);
    HDUIterator operator+(difference_type n) const;

#pragma warning(push)
#pragma warning(disable : 4146)
    inline HDUIterator& operator-=(difference_type n) { return *this += -n; }
    inline HDUIterator operator-(difference_type n) const { return *this + -n; }
#pragma warning(pop)

    difference_type operator-(const HDUIterator& other) const;

    reference operator[](difference_type n);

    bool operator<(const HDUIterator& other) const;
    inline bool operator>(const HDUIterator& other) const { return other < *this; }
    inline bool operator<=(const HDUIterator& other) const { return !(other < *this); }
    inline bool operator>=(const HDUIterator& other) const { return !(*this < other); }

private:
    FitsFile fits_;
    size_t hdu_index_;
};

inline void swap(HDUIterator& a, HDUIterator& b) { return a.swap(b); }

inline HDUIterator operator+(HDUIterator::difference_type n, const HDUIterator& it) {
    return it + n;
}
}  // namespace fits
