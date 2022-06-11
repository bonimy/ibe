#include "Environment.hxx"

// Local headers
#include "HttpException.hxx"
#include "format.hxx"
#include "get_env.hxx"

// Standard library
#include <iostream>
#include <typeinfo>
#include <utility>

namespace ibe {
namespace {
template <typename T>
T get_env(char const* name, T def) {
    char const* value = std::getenv(name);
    if (value) {
        try {
            return static_cast<T>(std::stoll(value));
        } catch (...) {
            throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                              format("%s could not be converted to a %s", name,
                                     typeid(T).name()));
        }
    } else {
        return def;
    }
}
}  // namespace

Environment::Environment(int argc, char const* const* argv)
        : content_length_(get_env<size_t>("CONTENT_LENGTH", 0)),
          server_port_(get_env<uint16_t>("SERVER_PORT", 0)),
          is_https_(get_env("HTTPS") == "on"),
          server_name_(get_env("SERVER_NAME")),
          gateway_interface_(get_env("GATEWAY_INTERFACE")),
          server_protocol_(get_env("SERVER_PROTOCOL")),
          request_method_(get_env("REQUEST_METHOD")),
          path_info_(get_env("PATH_INFO")),
          path_translated_(get_env("PATH_TRANSLATED")),
          script_name_(get_env("SCRIPT_NAME")),
          query_string_(get_env("QUERY_STRING")),
          content_type_(get_env("CONTENT_TYPE")),
          cookie_string_(get_env("HTTP_COOKIE")),
          kv_map_(),
          cookie_map_() {
    if (content_type_.empty() || content_type_ == "application/x-www-form-urlencoded") {
        parse_input(query_string_);
    } else if (content_type_.compare(0, 19, "multipart/form-data") == 0) {
        if (content_length_ == 0) {
            throw HTTP_EXCEPT(HttpResponseCode::LENGTH_REQUIRED,
                              "Content-Length is missing, 0 or invalid.");
        } else if (content_length_ > 65535) {
            throw HTTP_EXCEPT(HttpResponseCode::REQUEST_ENTITY_TOO_LARGE,
                              "Content-Length too large (file uploads not supported).");
        }
        char post_data[65536];
        std::cin.read(post_data, content_length_);
        parse_post_input(std::string(post_data, std::cin.gcount()));
    } else if (argc > 0 && argv != 0) {
        parse_input(std::string(argv[0]));
    } else {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                          "Invalid Request-Method and/or Content-Type.");
    }
    parse_cookies(cookie_string_);
}

Environment::~Environment() {}

/** Returns a vector of all the query parameter names.
 */
std::vector<std::string> const Environment::get_keys() const {
    std::vector<std::string> keys;
    keys.reserve(kv_map_.size());
    KeyValueIter i = kv_map_.begin();
    KeyValueIter const e = kv_map_.end();
    for (; i != e; ++i) {
        if (keys.size() == 0 || keys.back() != i->first) {
            keys.push_back(i->first);
        }
    }
    return keys;
}

/** Returns the first value of the query parameter with the given name.
 */
std::string const& Environment::get_value(std::string const& key) const {
    size_t n = get_num_values(key);
    if (n == 0) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                          format("No value specified for parameter %s", key.c_str()));
    } else if (n > 1) {
        throw HTTP_EXCEPT(
                HttpResponseCode::BAD_REQUEST,
                format("Multiple values specified for parameter %s", key.c_str()));
    }
    return kv_map_.find(key)->second;
}

/** Returns the first value of the query parameter with the given name, or
 * the specified default if the parameter is unavailable.
 */
std::string const Environment::get_value_or_default(std::string const& key,
                                                    std::string const& def) const {
    size_t n = get_num_values(key);
    if (n == 0) {
        return def;
    } else if (n > 1) {
        throw HTTP_EXCEPT(
                HttpResponseCode::BAD_REQUEST,
                format("Multiple values specified for parameter %s", key.c_str()));
    }
    return kv_map_.find(key)->second;
}

/** Returns the vector of values associated with the query parameter
 * of the given name.
 */
std::vector<std::string> const Environment::get_values(std::string const& key) const {
    std::vector<std::string> values;
    std::pair<KeyValueIter, KeyValueIter> const range = kv_map_.equal_range(key);
    for (KeyValueIter i = range.first; i != range.second; ++i) {
        values.push_back(i->second);
    }
    return values;
}

/** Returns a vector of all the cookie names.
 */
std::vector<std::string> const Environment::get_cookie_names() const {
    std::vector<std::string> names;
    names.reserve(cookie_map_.size());
    for (CookieIter i = cookie_map_.begin(), e = cookie_map_.end(); i != e; ++i) {
        names.push_back(i->first);
    }
    return names;
}

/** Returns the value of the cookie with the given name.
 */
std::string const& Environment::get_cookie(std::string const& name) const {
    CookieIter i = cookie_map_.find(name);
    if (i == cookie_map_.end()) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          format("No cookie named %s", name.c_str()));
    }
    return i->second;
}

/** Returns the value of the cookie with the given name, or the specified
 * default if no such cookie is available.
 */
std::string const Environment::get_cookie(std::string const& name,
                                          std::string const& def) const {
    CookieIter i = cookie_map_.find(name);
    return (i == cookie_map_.end()) ? def : i->second;
}

/** Returns a vector of all cookie (name, value) pairs sent along with the
 * request.
 */
std::vector<HttpCookie> const Environment::get_cookies() const {
    std::vector<HttpCookie> cookies;
    cookies.reserve(cookie_map_.size());
    for (CookieIter i = cookie_map_.begin(), e = cookie_map_.end(); i != e; ++i) {
        cookies.push_back(HttpCookie(i->first, i->second));
    }
    return cookies;
}

std::string const Environment::url_decode(std::string const& src) {
    std::string result;
    result.reserve(src.size());
    for (std::string::size_type i = 0, n = src.size(); i < n; ++i) {
        if (src[i] == '+') {
            result.append(1, ' ');
        } else if (src[i] != '%') {
            result.append(1, src[i]);
        } else {
            int c = '%';
            if (n - i > 2) {
                char c1 = src[i + 1];
                char c2 = src[i + 2];
                if (std::isxdigit(c1) && std::isxdigit(c2)) {
                    c = (c1 >= 'A' ? (c1 & 0xDF) - 'A' + 10 : c1 - '0') * 16;
                    c += (c2 >= 'A') ? (c2 & 0xDF) - 'A' + 10 : c2 - '0';
                    i += 2;
                }
            }
            result.append(1, static_cast<char>(c));
        }
    }
    return result;
}

void Environment::parse_input(std::string const& data) {
    if (data.empty()) {
        return;
    }
    std::string key, value;
    std::string::size_type prev = 0;

    while (true) {
        std::string::size_type i = data.find_first_of('=', prev);
        if (i == std::string::npos) {
            // no more key=value pairs
            break;
        }

        // decode key
        key = url_decode(data.substr(prev, i - prev));
        prev = i + 1;
        i = data.find_first_of('&', prev);
        if (i == std::string::npos) {
            value = data.substr(prev);
        } else {
            value = data.substr(prev, i - prev);
        }

        /// Do not decode 'path' because it has already been decoded
        /// once by Apache.  Double-decoding causes encoded plus '+'
        /// characters to become spaces ' '.
        if (key != "path") {
            value = url_decode(value);
        }
        kv_map_.insert(std::make_pair(key, value));
        if (i == std::string::npos) {
            break;
        }
        prev = i + 1;
    }
}

void Environment::parse_post_input(std::string const& data) {
    static std::string const boundary = "boundary=";
    static std::string const head_end = "\r\n\r\n";
    static std::string const cd = "Content-Disposition: form-data; ";
    static std::string const name = "name=\"";
    static std::string const filename = "filename=\"";

    std::string::size_type end, j, i = content_type_.find(boundary);
    std::string sep = "\r\n--";
    if (i == std::string::npos) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                          "Content-Type missing boundary specification");
    }
    i += boundary.size();
    if (content_type_[i] == '"') {
        i += 1;
        j = content_type_.find_first_of('"', i);
        if (j == std::string::npos) {
            throw HTTP_EXCEPT(
                    HttpResponseCode::BAD_REQUEST,
                    "Missing ending quote in Content-Type boundary specification");
        }
    } else {
        j = content_type_.find_first_of(';', i);
    }
    sep.append(content_type_, i, j - i);
    if (sep.size() > 74) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                          "Content-Type boundary specification too long");
    }
    end = data.rfind(sep);
    i = data.find(sep);
    while (i != std::string::npos) {
        i += sep.size();
        j = data.find(sep, i);
        if (j == std::string::npos) {
            break;
        }

        // Found a part that spans i to j
        std::string::size_type h = data.find(head_end, i);
        if (h == std::string::npos) {
            throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                              "Malformed multipart/form-data header");
        }
        h += head_end.size();

        // value spans [h, j). Parse Content-Disposition in header
        std::string::size_type nb = data.find(cd, i);
        if (nb >= h) {
            throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                              "Malformed multipart/form-data header");
        }
        nb += cd.size();
        if (data.find(filename, nb) < h) {
            throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                              "File uploads not supported");
        }
        nb = data.find(name, nb);
        if (nb > h) {
            throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                              "Malformed multipart/form-data header; "
                              "missing name in Content-Disposition");
        }
        nb += name.size();
        std::string::size_type ne = data.find_first_of('"', nb);
        if (ne >= h) {
            throw HTTP_EXCEPT(
                    HttpResponseCode::BAD_REQUEST,
                    "Malformed multipart/form-data header: "
                    "Content-Disposition name parameter missing ending quote");
        }
        kv_map_.insert(std::make_pair(data.substr(nb, ne - nb), data.substr(h, j - h)));
        i = j + sep.size();
        if (i < data.size() - 2 && data[i] == '-' && data[i + 1] == '-') {
            // found multipart epilogue separator
            break;
        }
    }
}

void Environment::parse_cookies(std::string const& data) {
    for (std::string::size_type i = 0, j = 0; j != std::string::npos; i = j + 1) {
        j = data.find(";", i);
        std::string::size_type sep = data.find("=", i);
        if (sep != std::string::npos && sep < j) {
            // eat whitespace
            for (; std::isspace(data[i]) != 0; ++i) {
            }
            if (i != sep) {
                if (j == std::string::npos) {
                    cookie_map_.insert(std::make_pair(data.substr(i, sep - i),
                                                      data.substr(sep + 1)));
                } else {
                    cookie_map_.insert(
                            std::make_pair(data.substr(i, sep - i),
                                           data.substr(sep + 1, j - sep - 1)));
                }
            }
        }
    }
}
}  // namespace ibe
