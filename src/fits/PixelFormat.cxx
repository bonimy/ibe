#include "PixelFormat.hxx"

// Standard library
#include <cmath>

namespace fits {
size_t sizeof_pixel(PixelFormat pixel_format) {
    return static_cast<size_t>(std::abs(static_cast<int>(pixel_format)) / 8);
}

TableDataType pixel_data_type(PixelFormat pixel_format) {
    switch (pixel_format) {
        case PixelFormat::byte_8bit:
            return TableDataType::byte_t;
        case PixelFormat::int_16bit:
            return TableDataType::short_t;
        case PixelFormat::int_32bit:
            return TableDataType::int32_t;
        case PixelFormat::float_32bit:
            return TableDataType::float_t;
        case PixelFormat::doublue_64bit:
            return TableDataType::double_t;
        default:
            return TableDataType::unknown;
    }
}

size_t sizeof_data_type(TableDataType data_type) {
    switch (data_type) {
        case fits::TableDataType::byte_t:
            return 1;
        case fits::TableDataType::sbyte_t:
            return 1;
        case fits::TableDataType::logical_t:
            return 4;
        case fits::TableDataType::ushort_t:
            return 2;
        case fits::TableDataType::short_t:
            return 2;
        case fits::TableDataType::uint_t:
            return 4;
        case fits::TableDataType::int_t:
            return 4;
        case fits::TableDataType::ulong_t:
            return 4;
        case fits::TableDataType::long_t:
            return 4;
        case fits::TableDataType::float_t:
            return 4;
        case fits::TableDataType::ulonglong_t:
            return 8;
        case fits::TableDataType::longlong_t:
            return 8;
        case fits::TableDataType::double_t:
            return 8;
        case fits::TableDataType::complex_t:
            return 8;
        case fits::TableDataType::complex_double_t:
            return 16;
        default:
            return 0;
    }
}
}  // namespace fits
