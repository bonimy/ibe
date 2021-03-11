#pragma once

// Standard library
#include <iostream>
#include <string>
#include <vector>

namespace fits {
/*
arstring - Fixed Size Array String

A string-like object whose container is a block of memory of fixed size.

Operates as a replacement for `char str[N];`. Implements operators to act like a
`std::string` object while not exceeding or truncating the storage size.

N - The size, in bytes, of reserved memory (including the null-terminaitng byte).
*/
template <size_t N>
class arstring {
public:
    constexpr static size_t capacity = N;

    using iterator = typename std::vector<char>::iterator;
    using const_iterator = typename std::vector<char>::const_iterator;

    // Allocates internal storage and sets all internal characters to '\0', making an
    // empty string.
    arstring();

    // Allocate internal storage and copy source string up to size of capacity.
    arstring(const char* str);
    arstring(const std::string& str);
    template <size_t M>
    arstring(const arstring<M>& right);

    arstring(const arstring&);
    arstring(arstring&&) noexcept;

    // Replace contents of string with source string, up to size of capacity.
    inline arstring& operator=(const char* right);
    inline arstring& operator=(const std::string& right);
    template <size_t M>
    inline arstring& operator=(const arstring<M>& right);

    inline arstring& operator=(arstring&);
    inline arstring& operator=(arstring&&) noexcept;

    // Determine whether two string are equal or unequal up to size of capacity.
    inline bool operator==(const char* right) const;
    inline bool operator!=(const char* right) const;

    inline bool operator==(const std::string& right) const;
    inline bool operator!=(const std::string& right) const;

    template <size_t M>
    inline bool operator==(const arstring<M>& right) const;
    template <size_t M>
    inline bool operator!=(const arstring<M>& right) const;

    // Determines whether the size of the string is zero.
    inline bool empty() const;

    // Gets the length of the string, up to size of capacity.
    inline size_t size() const;

    inline char& operator[](size_t index);
    inline const char& operator[](size_t index) const;

    inline operator char*();
    inline operator const char*() const;

    inline operator std::string();
    inline operator const std::string() const;

    // Return an iterator pointing to (*this_)[0] or (*this)[capacity].
    inline iterator begin();
    inline iterator end();

    inline const_iterator begin() const;
    inline const_iterator end() const;

    inline const_iterator cbegin() const;
    inline const_iterator cend() const;

private:
    std::vector<char> str_;
};

template <size_t N>
inline bool operator==(const char* left, const arstring<N>& right);
template <size_t N>
inline bool operator!=(const char* left, const arstring<N>& right);

template <size_t N>
inline bool operator==(const std::string& left, const arstring<N>& right);
template <size_t N>
inline bool operator!=(const std::string& left, const arstring<N>& right);

template <size_t N, class Elem, class Traits>
inline std::basic_ostream<Elem, Traits>& operator<<(std::basic_ostream<Elem, Traits>& s,
                                                    const arstring<N>& str);

template <size_t N, class Elem, class Traits>
inline std::basic_istream<Elem, Traits>& operator>>(std::basic_istream<Elem, Traits>& s,
                                                    const arstring<N>& str);
}  // namespace fits

#include "arstring.inl"
