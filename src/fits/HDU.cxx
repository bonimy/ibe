#include "fits/HDU.hxx"

// Standard library
#include <algorithm>
#include <cstdlib>
#include <functional>
#include <numeric>

// Local headers
#include "fits/FitsError.hxx"
#include "fits/PixelFormat.hxx"

namespace fits {
HDU::HDU(FitsFile& owner, size_t hdu_num) : owner_(owner), hdu_num_(hdu_num) {}

bool HDU::operator==(const HDU& other) const {
    return owner_ == other.owner_ && hdu_num_ == other.hdu_num_;
}
bool HDU::operator!=(const HDU& other) const { return !(*this == other); }

FitsFile& HDU::owner() { return owner_; }
const FitsFile& HDU::owner() const { return owner_; }

size_t HDU::hdu_num() const { return hdu_num_; }

size_t HDU::naxis() {
    make_current();

    int result;
    int status = 0;
    if (fits_get_img_dim(&owner_, &result, &status) > 0) {
        throw FitsError(status);
    }
    return static_cast<size_t>(result);
}
std::vector<long> HDU::naxes() {
    make_current();

    std::vector<long> result(naxis());
    int status = 0;
    if (fits_get_img_size(&owner_, static_cast<int>(result.size()), result.data(),
                          &status) > 0) {
        throw FitsError(status);
    }
    return result;
}

HDU::Type HDU::ext_type() {
    make_current();

    int status = 0;
    int ext_type;
    if (fits_get_hdu_type(&owner_, &ext_type, &status) > 0) {
        throw FitsError(status);
    }
    return static_cast<Type>(ext_type);
}

PixelFormat HDU::bit_pix() { return pixel_format(); }
PixelFormat HDU::pixel_format() {
    make_current();

    int status = 0;
    int result;
    if (fits_get_img_type(&owner_, &result, &status) > 0) {
        throw FitsError(status);
    }
    return static_cast<PixelFormat>(result);
}

void HDU::make_current() { owner_.make_hdu_current(hdu_num_); }

size_t HDU::keyword_count() {
    make_current();

    int status = 0;
    int size;
    if (fits_get_hdrpos(&owner_, &size, nullptr, &status) > 0) {
        throw FitsError(status);
    }
    return static_cast<size_t>(size);
}
Keyword HDU::read_keyword(size_t index) {
    make_current();

    int status = 0;
    Keyword result;
    if (fits_read_keyn(&owner_, static_cast<int>(index + 1), result.name, result.value,
                       result.comment, &status) > 0) {
        throw FitsError(status);
    }
    return result;
}
card_str HDU::read_card(const key_str& key) {
    make_current();

    card_str result;
    int status = 0;
    if (fits_read_card(&owner_, key, result, &status) > 0) {
        throw FitsError(status);
    }
    return result;
}
std::vector<Keyword> HDU::read_keys() {
    std::vector<Keyword> result(keyword_count());
    for (size_t i = 0; i < result.size(); i++) {
        result[i] = read_keyword(i);
    }
    return result;
}

void HDU::write_card(const card_str& card) {
    make_current();

    int status = 0;
    if (fits_write_record(&owner_, card, &status) > 0) {
        throw FitsError(status);
    }
}
void HDU::write_key(const Keyword& keyword) {
    make_current();

    int status = 0;
    card_str card;
    if (fits_make_key(keyword.name, const_cast<value_str&>(keyword.value),
                      keyword.comment, card, &status) > 0) {
        throw FitsError(status);
    }
    if (fits_write_record(&owner_, card, &status) > 0) {
        throw FitsError(status);
    }
}
void HDU::write_float(const card_str& name, float value, const comment_str& comment) {
    make_current();

    int status = 0;
    if (fits_write_key_flt(&owner_, name, value, 9, comment, &status) > 0) {
        throw FitsError(status);
    }
}

bool HDU::is_compressed_image() {
    make_current();

    int status = 0;
    return static_cast<bool>(fits_is_compressed_image(&owner_, &status));
}

void HDU::clear_bscale() { set_bscale(1, 0); }
void HDU::set_bscale(double scale, double offset) {
    make_current();

    int status = 0;
    if (fits_set_bscale(&owner_, scale, offset, &status) > 0) {
        throw FitsError(status);
    }
}

Buffer<void> HDU::read_image_subset(const std::vector<long>& first,
                                    const std::vector<long>& last) {
    return read_image_subset(pixel_data_type(pixel_format()), first, last);
}
Buffer<void> HDU::read_image_subset(TableDataType pixel_type,
                                    const std::vector<long>& first,
                                    const std::vector<long>& last) {
    bool discard = false;
    return read_image_subset(pixel_type, first, last, nullptr, discard);
}
Buffer<void> HDU::read_image_subset(const std::vector<long>& first,
                                    const std::vector<long>& last, void* null_value,
                                    bool& any_null) {
    return read_image_subset(pixel_data_type(pixel_format()), first, last, null_value,
                             any_null);
}
Buffer<void> HDU::read_image_subset(TableDataType pixel_type,
                                    const std::vector<long>& first,
                                    const std::vector<long>& last, void* null_value,
                                    bool& any_null) {
    return read_image_subset(pixel_type, first, last,
                             std::vector<long>(first.size(), 1l), null_value, any_null);
}
Buffer<void> HDU::read_image_subset(const std::vector<long>& first,
                                    const std::vector<long>& last,
                                    const std::vector<long>& increment) {
    return read_image_subset(pixel_data_type(pixel_format()), first, last, increment);
}
Buffer<void> HDU::read_image_subset(TableDataType pixel_type,
                                    const std::vector<long>& first,
                                    const std::vector<long>& last,
                                    const std::vector<long>& increment) {
    bool discard = false;
    return read_image_subset(pixel_type, first, last, increment, nullptr, discard);
}
Buffer<void> HDU::read_image_subset(const std::vector<long>& first,
                                    const std::vector<long>& last,
                                    const std::vector<long>& increment,
                                    void* null_value, bool& any_null) {
    return read_image_subset(pixel_data_type(pixel_format()), first, last, increment,
                             null_value, any_null);
}
Buffer<void> HDU::read_image_subset(TableDataType pixel_type,
                                    const std::vector<long>& first,
                                    const std::vector<long>& last,
                                    const std::vector<long>& increment,
                                    void* null_value, bool& any_null) {
    make_current();

    // Get the size of each dimension
    std::vector<long> box = last;
    std::transform(last.begin(), last.end(), first.begin(), box.begin(),
                   [](long a, long b) { return 1 + a - b; });

    // Buffer size should be product of all axes and bitpix size.
    size_t pixel_size = sizeof_data_type(pixel_type);
    size_t buffer_size = pixel_size;
    buffer_size = std::accumulate(box.begin(), box.end(), buffer_size,
                                  std::multiplies<size_t>());

    // Check that an overflow did not occur.
    if (std::accumulate(box.begin(), box.end(), buffer_size, std::divides<size_t>()) !=
        pixel_size) {
        throw std::overflow_error("Buffer<void> size exceeds 64-bits.");
    }

    Buffer<void> buffer(buffer_size);

    int status = 0;
    int anynul = static_cast<int>(any_null);
    if (fits_read_subset(
                &owner_, static_cast<int>(pixel_type), const_cast<long*>(first.data()),
                const_cast<long*>(last.data()), const_cast<long*>(increment.data()),
                null_value, buffer.get(), &anynul, &status) > 0) {
        throw FitsError(status);
    }
    any_null = static_cast<bool>(anynul);

    return buffer;
}

void HDU::write_image_subset(const std::vector<long>& first,
                             const std::vector<long>& last,
                             const Buffer<void>& buffer) {
    write_image_subset(pixel_data_type(pixel_format()), first, last, buffer);
}
void HDU::write_image_subset(TableDataType pixel_type, const std::vector<long>& first,
                             const std::vector<long>& last,
                             const Buffer<void>& buffer) {
    make_current();

    int status = 0;
    if (fits_write_subset(&owner_, static_cast<int>(pixel_type),
                          const_cast<long*>(first.data()),
                          const_cast<long*>(last.data()),
                          const_cast<void*>(buffer.get()), &status) > 0) {
        throw FitsError(status);
    }
}
}  // namespace fits
