#include "format.hxx"

// Standard library
#include <cstdarg>
#include <cstdio>
#include <vector>

namespace ibe {
std::string const format(char const* fmt, ...) {
    static std::string const FAILED = "Failed to format message";
    struct VarArgs {
        std::va_list* ap;
        VarArgs(std::va_list& list) : ap(&list) {}
        ~VarArgs() { va_end(*ap); }
    };

    std::va_list list;
    char buf[256];
    VarArgs args(list);

    // Try formatting using a stack allocated buffer
    va_start(list, fmt);
    int n = ::vsnprintf(buf, sizeof(buf), fmt, list);
    try {
        if (n >= static_cast<int>(sizeof(buf))) {

            // buf was too small, allocate the necessary memory on the heap
            std::vector<char> bigbuf(n + 1);
            va_end(list);
            va_start(list, fmt);
            if (::vsnprintf(bigbuf.data(), static_cast<size_t>(n + 1), fmt, list) >=
                0) {
                return std::string(bigbuf.data());
            }
        } else if (n >= 0) {
            return std::string(buf);
        }
    } catch (...) {
    }
    return FAILED;
}
}  // namespace ibe
