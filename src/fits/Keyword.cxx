#include "Keyword.hxx"

// Local headers
#include "FitsError.hxx"

// Standard library
#include <cstring>

namespace fits {
Keyword::Keyword() = default;

Keyword::Keyword(const key_str& name, const value_str& value,
                 const comment_str& comment)
        : name(name), value(value), comment(comment) {}

Keyword::Keyword(const card_str& card) : Keyword() {
    int status = 0;
    int length;

    if (fits_get_keyname(const_cast<card_str&>(card), name, &length, &status) > 0) {
        throw FitsError(status);
    }
    if (fits_parse_value(const_cast<card_str&>(card), value, comment, &status) > 0) {
        throw FitsError(status);
    }
}

bool Keyword::operator==(const Keyword& right) const {
    return name == right.name && value == right.value && comment == right.comment;
}
bool Keyword::operator!=(const Keyword& right) const { return !(*this == right); }
}  // namespace fits
