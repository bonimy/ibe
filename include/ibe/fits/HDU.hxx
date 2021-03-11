#pragma once

// Standard library
#include <cstdlib>
#include <memory>
#include <string>
#include <type_traits>
#include <vector>

// Local headers
#include "Buffer.hxx"
#include "FitsFile.hxx"
#include "Keyword.hxx"

namespace fits {
class HDU {
public:
    enum class Type {
        image = IMAGE_HDU,
        ascii = ASCII_TBL,
        binary = BINARY_TBL,
        any = ANY_HDU,
    };

    HDU(FitsFile& owner, size_t hdu);

    bool operator==(const HDU& other) const;
    inline bool operator!=(const HDU& other) const;

    FitsFile& owner();
    const FitsFile& owner() const;

    size_t hdu_num() const;

    size_t naxis();
    std::vector<long> naxes();

    Type ext_type();

    PixelFormat bit_pix();
    PixelFormat pixel_format();

    void make_current();

    size_t keyword_count();
    Keyword read_keyword(size_t index);
    card_str read_card(const key_str& key);
    std::vector<Keyword> read_keys();

    void write_card(const card_str& card);
    void write_key(const Keyword& keyword);
    void write_float(const card_str& name, float value, const comment_str& comment);

    bool is_compressed_image();

    void clear_bscale();
    void set_bscale(double scale, double offset);

    Buffer<void> read_image_subset(const std::vector<long>& first,
                                   const std::vector<long>& last);
    Buffer<void> read_image_subset(TableDataType pixel_type,
                                   const std::vector<long>& first,
                                   const std::vector<long>& last);
    Buffer<void> read_image_subset(const std::vector<long>& first,
                                   const std::vector<long>& last, void* null_value,
                                   bool& any_null);
    Buffer<void> read_image_subset(TableDataType pixel_type,
                                   const std::vector<long>& first,
                                   const std::vector<long>& last, void* null_value,
                                   bool& any_null);
    Buffer<void> read_image_subset(const std::vector<long>& first,
                                   const std::vector<long>& last,
                                   const std::vector<long>& increment);
    Buffer<void> read_image_subset(TableDataType pixel_type,
                                   const std::vector<long>& first,
                                   const std::vector<long>& last,
                                   const std::vector<long>& increment);
    Buffer<void> read_image_subset(const std::vector<long>& first,
                                   const std::vector<long>& last,
                                   const std::vector<long>& increment, void* null_value,
                                   bool& any_null);
    Buffer<void> read_image_subset(TableDataType pixel_type,
                                   const std::vector<long>& first,
                                   const std::vector<long>& last,
                                   const std::vector<long>& increment, void* null_value,
                                   bool& any_null);

    void write_image_subset(const std::vector<long>& first,
                            const std::vector<long>& last, const Buffer<void>& buffer);
    void write_image_subset(TableDataType pixel_type, const std::vector<long>& first,
                            const std::vector<long>& last, const Buffer<void>& buffer);

private:
    FitsFile owner_;
    size_t hdu_num_;

    friend class FitsFile;
};
}  // namespace fits
