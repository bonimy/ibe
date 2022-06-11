#pragma once

// Local headers
#include "Writer.hxx"

namespace ibe {
/** Writes chunked output to standard out.
 */
class ChunkedWriter : public Writer {
public:
    ChunkedWriter() {}
    virtual ~ChunkedWriter();

    virtual void write(unsigned char const* const buf, size_t const len);
    virtual void finish();

private:
    // disable copy construction and assignment
    ChunkedWriter(ChunkedWriter const&) = delete;
    ChunkedWriter& operator=(ChunkedWriter const&) = delete;
};
}  // namespace ibe
