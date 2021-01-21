#include <boost/regex.hpp>
#include <boost/shared_ptr.hpp>

#include "Cgi.hxx"
#include "Coords.hxx"

using std::string;

namespace ibe {

namespace {

// Regular expressions for recognizing various units.
boost::regex const _pixRe("^(px?|pix(?:els?)?)\\s*$");
boost::regex const _arcsecRe("^(\"|a(rc)?-?sec(onds?)?)\\s*$");
boost::regex const _arcminRe("^('|a(rc)?-?min(utes?)?)\\s*$");
boost::regex const _degRe("^(d(?:eg(?:rees?)?)?)\\s*$");
boost::regex const _radRe("^rad(ians?)?\\s*$");

}  // unnamed namespace

#define PP_MSG                                                                  \
    format("Value of %s parameter must consist of %s comma separated floating " \
           "point numbers, followed by an optional units specification.",       \
           key.c_str(), requirePair ? "2" : "1 or 2")

Coords const parse_coords(Environment const& env, string const& key, Units defaultUnits,
                          bool requirePair) {
    Coords coords;
    char* s = 0;

    string const value = env.getValue(key);
    string::size_type comma = value.find(',');
    if (comma == string::npos && requirePair) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST, PP_MSG);
    }
    // get value of first coordinate
    coords.c[0] = std::strtod(value.c_str(), &s);
    if (s == 0 || s == value.c_str()) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST, PP_MSG);
    }
    if (requirePair || comma != string::npos) {
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
    coords.units = defaultUnits;
    for (; std::isspace(*s); ++s) {
    }
    if (*s != 0) {
        // parse unit specification
        if (boost::regex_match(s, _pixRe)) {
            coords.units = PIX;
        } else if (boost::regex_match(s, _arcsecRe)) {
            coords.units = ARCSEC;
        } else if (boost::regex_match(s, _arcminRe)) {
            coords.units = ARCMIN;
        } else if (boost::regex_match(s, _degRe)) {
            coords.units = DEG;
        } else if (boost::regex_match(s, _radRe)) {
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

#undef PP_MSG
}  // namespace ibe
