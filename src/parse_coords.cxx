#include "parse_coords.hxx"

// Local headers
#include "HttpException.hxx"
#include "HttpResponseCode.hxx"
#include "format.hxx"

// Standard library
#include <regex>

#define PP_MSG                                                                  \
    format("Value of %s parameter must consist of %s comma separated floating " \
           "point numbers, followed by an optional units specification.",       \
           key.c_str(), require_pair ? "2" : "1 or 2")

using std::string;

namespace ibe {
namespace {

// Regular expressions for recognizing various units.
std::regex const pix_re("^(px?|pix(?:els?)?)\\s*$");
std::regex const arcsec_re("^(\"|a(rc)?-?sec(onds?)?)\\s*$");
std::regex const arcmin_re("^('|a(rc)?-?min(utes?)?)\\s*$");
std::regex const deg_re("^(d(?:eg(?:rees?)?)?)\\s*$");
std::regex const rad_re("^rad(ians?)?\\s*$");
}  // unnamed namespace

Coords const parse_coords(Environment const& env, string const& key,
                          Units default_units, bool require_pair) {
    Coords coords;
    char* s = 0;

    string const value = env.get_value(key);
    string::size_type comma = value.find(',');
    if (comma == string::npos && require_pair) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST, PP_MSG);
    }

    // get value of first coordinate
    coords.c[0] = std::strtod(value.c_str(), &s);
    if (s == 0 || s == value.c_str()) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST, PP_MSG);
    }
    if (require_pair || comma != string::npos) {
        // get value of second coordinate
        for (; std::isspace(*s); ++s) {
        }
        if (static_cast<string::size_type>(s - value.c_str()) != comma) {
            throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST, PP_MSG);
        }
        coords.c[1] = std::strtod(value.c_str() + (comma + 1), &s);
        if (s == 0 || s == value.c_str() + (comma + 1)) {
            throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST, PP_MSG);
        }
    } else {
        // single coordinate value passed in
        coords.c[1] = coords.c[0];
    }
    coords.units = default_units;
    for (; std::isspace(*s); ++s) {
    }
    if (*s != 0) {
        // parse unit specification
        if (std::regex_match(s, pix_re)) {
            coords.units = PIX;
        } else if (std::regex_match(s, arcsec_re)) {
            coords.units = ARCSEC;
        } else if (std::regex_match(s, arcmin_re)) {
            coords.units = ARCMIN;
        } else if (std::regex_match(s, deg_re)) {
            coords.units = DEG;
        } else if (std::regex_match(s, rad_re)) {
            coords.units = RAD;
        } else {
            throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                              format("Value of %s parameter has invalid trailing unit "
                                     "specification",
                                     key.c_str()));
        }
    }
    return coords;
}
}  // namespace ibe
