#pragma once

// Third-party headers
#include <fitsio.h>

namespace fits {

// Bit formats for FITS Images.
enum class PixelFormat {
    unknown = 0,
    byte_8bit = BYTE_IMG,
    int_16bit = SHORT_IMG,
    int_32bit = LONG_IMG,
    int_64bit = LONGLONG_IMG,
    float_32bit = FLOAT_IMG,
    doublue_64bit = DOUBLE_IMG,
    sbyte_8bit = SBYTE_IMG,
    uint_16bit = USHORT_IMG,
    uint_32bit = ULONG_IMG,
    uint_64bit = ULONGLONG_IMG,
};

// Codes for FITS Table data types.
enum class TableDataType {
    unknown = 0,
    bit_t = TBIT,
    byte_t = TBYTE,
    sbyte_t = TSBYTE,
    logical_t = TLOGICAL,
    string_t = TSTRING,
    ushort_t = TUSHORT,
    short_t = TSHORT,
    uint_t = TUINT,
    int_t = TINT,
    ulong_t = TULONG,
    long_t = TLONG,
    int32_t = TINT32BIT,
    float_t = TFLOAT,
    ulonglong_t = TULONGLONG,
    longlong_t = TLONGLONG,
    double_t = TDOUBLE,
    complex_t = TCOMPLEX,
    complex_double_t = TDBLCOMPLEX,
};

// Get the data type of a given pixel format.
TableDataType pixel_data_type(PixelFormat pixel_format);

// Gets the size, in bytes, of a pixel format.
size_t sizeof_pixel(PixelFormat pixel_format);

// Gets the size, in bytes, of a data type.
// Returns 0 for bit and string types.
size_t sizeof_data_type(TableDataType data_type);
}  // namespace fits
