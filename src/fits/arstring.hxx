#pragma once

// Standard library
#include <cstring>
#include <istream>
#include <iterator>
#include <ostream>
#include <string>

namespace fits {
/*
arstring - Fixed Size Array String

A string-like object whose container is a block of memory of fixed size.

Operates as a replacement for `char str[N];`. Implements operators to act like a
`std::string` object while not exceeding or truncating the storage size.

N - The size, in bytes, of reserved memory (including the null-terminating byte).
*/
template <size_t N>
class arstring {
public:
    constexpr static size_t capacity = N;

    typedef char* iterator;
    typedef const char* const_iterator;

    typedef std::reverse_iterator<iterator> reverse_iterator;
    typedef std::reverse_iterator<const_iterator> const_reverse_iterator;

    // Allocates internal storage and sets all internal characters to '\0', making an
    // empty string.
    arstring() { *str_ = '\0'; }

    // Allocate internal storage and copy source string up to size of capacity.
    arstring(const char* str) : arstring() { std::strncpy(str_, str, capacity); }
    arstring(const std::string& str) : arstring(str.c_str()) {}
    template <size_t M>
    arstring(const arstring<M>& right) : arstring(static_cast<const char*>(right)) {}

    arstring(const arstring& right) : arstring(right.str_) {}

    // Replace contents of string with source string, up to size of capacity.
    arstring& operator=(const char* right) {
        std::strncpy(str_, right, capacity);
        return *this;
    }
    arstring& operator=(const std::string& right) { return *this = right.c_str(); }
    template <size_t M>
    arstring& operator=(const arstring<M>& right) {
        return *this = static_cast<const char*>(right);
    }

    arstring& operator=(arstring& right) { return *this = right.str_; }

    // Determine whether two string are equal or unequal up to size of capacity.
    bool operator==(const char* right) const {
        return std::strncmp(str_, right, capacity) == 0;
    }
    bool operator!=(const char* right) const { return !(*this == right); }

    bool operator==(const std::string& right) const { return *this == right.c_str(); }
    bool operator!=(const std::string& right) const { return !(*this == right); }

    template <size_t M>
    bool operator==(const arstring<M>& right) const {
        return *this == static_cast<const char*>(right);
    }
    template <size_t M>
    bool operator!=(const arstring<M>& right) const {
        return !(*this == right);
    }

    // Determines whether the size of the string is zero.
    bool empty() const noexcept { return *str_ == '\0'; }

    // Gets the length of the string, up to size of capacity.
    size_t size() const noexcept {
        // Cannot use `std::strlen` since there's risk of exceeding memory storage.
        for (size_t i = 0; i < capacity; i++) {
            if (str_[i] == '\0') return i;
        }
        return capacity + 1;
    }

    char& operator[](size_t index) { return str_[index]; }
    const char& operator[](size_t index) const { return str_[index]; }

    operator char*() noexcept { return str_; }
    operator const char*() const noexcept { return str_; }

    operator std::string() { return str_; }
    operator const std::string() const { return str_; }

    iterator begin() noexcept { return std::begin(str_); }
    iterator end() noexcept { return std::end(str_); }

    const_iterator begin() const noexcept { return std::begin(str_); }
    const_iterator end() const noexcept { return std::end(str_); }

    const_iterator cbegin() const noexcept { return std::cbegin(str_); }
    const_iterator cend() const noexcept { return std::cend(str_); }

    reverse_iterator rbegin() noexcept { return std::rbegin(str_); }
    reverse_iterator rend() noexcept { return std::rend(str_); }

    const_reverse_iterator rbegin() const noexcept { return std::rbegin(str_); }
    const_reverse_iterator rend() const noexcept { return std::rend(str_); }

    const_reverse_iterator crbegin() const noexcept { return std::crbegin(str_); }
    const_reverse_iterator crend() const noexcept { return std::crend(str_); }

private:
    char str_[capacity];
};

template <size_t N>
inline bool operator==(const char* left, const arstring<N>& right) {
    return right == left;
}
template <size_t N>
inline bool operator!=(const char* left, const arstring<N>& right) {
    return right != left;
}

template <size_t N>
inline bool operator==(const std::string& left, const arstring<N>& right) {
    return right == left;
}
template <size_t N>
inline bool operator!=(const std::string& left, const arstring<N>& right) {
    return right != left;
}

template <size_t N>
inline std::ostream& operator<<(std::ostream& s, const arstring<N>& str) {
    return s << static_cast<const char*>(str);
}

template <size_t N>
inline std::istream& operator>>(std::istream& s, const arstring<N>& str) {
    return s >> static_cast<const char*>(str);
}
}  // namespace fits
