#pragma once

namespace ibe {
/** Base class for output writers.
 */
class Writer {
public:
    virtual ~Writer();

    virtual void write(unsigned char const* const buf, size_t const len) = 0;
    virtual void finish() = 0;
};
}  // namespace ibe
