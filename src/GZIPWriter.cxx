#include "GZIPWriter.hxx"

// Local headers
#include "HttpException.hxx"
#include "HttpResponseCode.hxx"
#include "format.hxx"

namespace ibe {
GZIPWriter::GZIPWriter(Writer& writer, size_t const chunk_size)
        : writer_(&writer), chunk_size_(chunk_size), stream_(), buffer_() {
    std::vector<unsigned char> mem(chunk_size);

    // setup zlib (15 window bits, add 16 to indicate a gzip compatible header is
    // desired)
    if (::deflateInit2(&stream_, 1, Z_DEFLATED, MAX_WBITS + 16, MAX_MEM_LEVEL,
                       Z_DEFAULT_STRATEGY) != Z_OK) {
        throw HTTP_EXCEPT(
                HttpResponseCode::INTERNAL_SERVER_ERROR,
                "[zlib] deflateInit2() failed to initialize compression stream");
    }
    swap(buffer_, mem);
    stream_.next_out = buffer_.data();
    stream_.avail_out = chunk_size_;
}

GZIPWriter::~GZIPWriter() { ::deflateEnd(&stream_); }

void GZIPWriter::write(unsigned char const* const buf, size_t const len) {
    if (buf == 0 || len == 0) {
        return;
    }
    stream_.next_in = const_cast<Bytef*>(buf);
    stream_.avail_in = len;

    // deflate/write until the buffer passed in by the user has been consumed
    do {
        int const zret = ::deflate(&stream_, Z_NO_FLUSH);
        if (zret != Z_OK) {
            throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                              format("[zlib] deflate() failed, return code: %d", zret));
        }
        if (stream_.avail_out != 0) {
            if (stream_.avail_in != 0) {
                throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                                  "[zlib] deflate() failed to consume input");
            }
            break;
        }

        // no more space left in _buffer, write it out
        writer_->write(buffer_.data(), chunk_size_);
        stream_.next_out = buffer_.data();
        stream_.avail_out = chunk_size_;
    } while (stream_.avail_in != 0);
}

void GZIPWriter::finish() {
    if (stream_.avail_out == 0) {
        writer_->write(buffer_.data(), chunk_size_);
        stream_.next_out = buffer_.data();
        stream_.avail_out = chunk_size_;
    }
    while (true) {
        int const zret = ::deflate(&stream_, Z_FINISH);
        if (zret == Z_STREAM_END) {
            writer_->write(buffer_.data(), chunk_size_ - stream_.avail_out);
            break;
        } else if (zret == Z_OK) {
            if (stream_.avail_out != 0) {
                throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                                  "[zlib] deflate() failed to fill output buffer");
            }
            writer_->write(buffer_.data(), chunk_size_);
            stream_.next_out = buffer_.data();
            stream_.avail_out = chunk_size_;
        } else {
            throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                              format("[zlib] deflate() failed, return code: %d", zret));
        }
    }
    writer_->finish();
}
}  // namespace ibe
