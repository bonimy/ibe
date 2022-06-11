#pragma once

// Standard library
#include <cstdlib>
#include <memory>

namespace fits {
template <class T>
struct BufferDeleter {
    using element_type = T;
    using pointer = T*;

    void operator()(pointer ptr) { std::free(static_cast<void*>(ptr)); }
};

template <class T>
class Buffer : public std::unique_ptr<T, BufferDeleter<T>> {
public:
    Buffer(size_t size)
            : std::unique_ptr<T, BufferDeleter<T>>(static_cast<T*>(std::malloc(size))) {
    }
};
}  // namespace fits
