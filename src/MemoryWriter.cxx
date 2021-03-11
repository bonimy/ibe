#include "MemoryWriter.hxx"

// Standard library
#include <algorithm>
#include <cstdlib>
#include <cstring>

// Local headers
#include "HttpException.hxx"
#include "HttpResponseCode.hxx"

namespace ibe {
MemoryWriter::MemoryWriter() : content_length_(0), cap_(1024 * 1024), content_(0) {
    content_ = (unsigned char*)std::malloc(cap_);
    if (content_ == 0) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "memory allocation failed");
    }
}

MemoryWriter::~MemoryWriter() { std::free(content_); }

void MemoryWriter::write(unsigned char const* const buf, size_t const len) {
    if (content_length_ + len < content_length_) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "too much data to buffer in memory");
    } else if (content_length_ + len > cap_) {
        size_t nc = std::max(2 * cap_, content_length_ + len);
        unsigned char* c = (unsigned char*)std::realloc(content_, nc);
        if (c == 0) {
            throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                              "memory reallocation failed");
        }
        content_ = c;
        cap_ = nc;
    }
    std::memcpy(content_ + content_length_, buf, len);
    content_length_ += len;
}

void MemoryWriter::finish() {}
}  // namespace ibe
