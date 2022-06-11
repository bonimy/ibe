#pragma once

// Local headers
#include "Writer.hxx"

namespace ibe {
/** Writes output to an in-memory buffer.
 */
class MemoryWriter : public Writer {
public:
    MemoryWriter();
    virtual ~MemoryWriter();

    virtual void write(unsigned char const* const buf, size_t const len);
    virtual void finish();
    size_t get_content_length() const { return content_length_; }
    unsigned char const* get_content() const { return content_; }

private:
    // disable copy construction and assignment
    MemoryWriter(MemoryWriter const&) = delete;
    MemoryWriter& operator=(MemoryWriter const&) = delete;

    size_t content_length_;
    size_t cap_;
    unsigned char* content_;
};
}  // namespace ibe
