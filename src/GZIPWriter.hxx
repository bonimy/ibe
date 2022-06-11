#pragma once

// Local headers
#include "Writer.hxx"

// External APIs
#include <zlib/zlib.h>
#if ZLIB_VERNUM < 0x123
#warning Older version of zlib detected, upgrading to version 1.2.3 or later is recommended
#endif

// Standard library
#include <vector>

namespace ibe {
/** Writes chunked, GZIP compressed output to another writer.
 */
class GZIPWriter : public Writer {
public:
    explicit GZIPWriter(Writer& writer, size_t const chunk_size = 8192);
    virtual ~GZIPWriter();

    virtual void write(unsigned char const* const buf, size_t const size);
    virtual void finish();

    size_t get_chunk_size() const { return chunk_size_; }

private:
    // disable copy construction and assignment
    GZIPWriter(GZIPWriter const&) = delete;
    GZIPWriter& operator=(GZIPWriter const&) = delete;

    Writer* writer_;
    size_t const chunk_size_;            ///< output granularity
    z_stream stream_;                    ///< zlib state
    std::vector<unsigned char> buffer_;  ///< compressed output buffer
};
}  // namespace ibe
