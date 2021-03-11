namespace fits {
template <class T>
void BufferDeleter<T>::operator()(pointer ptr) {
    std::free(static_cast<void*>(ptr));
}

template <class T>
Buffer<T>::Buffer(size_t size)
        : std::unique_ptr<T, BufferDeleter<T>>(static_cast<T*>(std::malloc(size))) {}
}  // namespace fits
