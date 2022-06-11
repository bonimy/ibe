#pragma once

// Local headers
#include "arstring.hxx"

// External APIs
#include <fitsio.h>

namespace fits {
using card_str = arstring<FLEN_CARD>;
using key_str = arstring<FLEN_KEYWORD>;
using value_str = arstring<FLEN_VALUE>;
using comment_str = arstring<FLEN_COMMENT>;

struct Keyword {
    key_str name;
    value_str value;
    comment_str comment;

    Keyword();

    Keyword(const key_str& name, const value_str& value, const comment_str& comment);

    Keyword(const card_str& card);

    bool operator==(const Keyword& right) const;
    bool operator!=(const Keyword& right) const;
};
}  // namespace fits
