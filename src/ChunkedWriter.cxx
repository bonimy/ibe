#include "ChunkedWriter.hxx"

// Local headers
#include "HttpException.hxx"
#include "HttpResponseCode.hxx"

// Standard library
#include <cstdio>

namespace ibe {
ChunkedWriter::~ChunkedWriter() {}

void ChunkedWriter::write(unsigned char const* const buf, size_t const len) {
    if (buf == 0 || len == 0) {
        return;
    }
    if (std::printf("%llX\r\n", static_cast<unsigned long long>(len)) < 0) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "failed to write to standard out");
    }
    if (std::fwrite(buf, len, 1, stdout) != 1) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "failed to write to standard out");
    }
    if (std::fwrite("\r\n", 2, 1, stdout) != 1) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "failed to write to standard out");
    }
}

void ChunkedWriter::finish() {
    if (std::fwrite("0\r\n\r\n", 5, 1, stdout) != 1) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "failed to write to standard out");
    }
    std::fflush(stdout);
}
}  // namespace ibe
