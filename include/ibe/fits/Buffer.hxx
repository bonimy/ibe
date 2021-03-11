#pragma once

#include <cstdlib>
#include <memory>

namespace fits {
template <class T>
struct BufferDeleter {
    using element_type = T;
    using pointer = T*;

    void operator()(pointer ptr);
};

template <class T>
class Buffer : public std::unique_ptr<T, BufferDeleter<T>> {
public:
    Buffer(size_t size);
};
}  // namespace fits

#include "Buffer.inl"
