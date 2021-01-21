/** @file
 * @brief  Minimalistic CGI request handling library implementation.
 * @author Serge Monkewitz
 */
#include "Cgi.hxx"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>

#include "boost/lexical_cast.hpp"
#include "boost/scoped_array.hpp"

using std::cin;
using std::cout;
using std::endl;
using std::ostream;
using std::ostringstream;
using std::pair;
using std::string;
using std::swap;
using std::vector;

namespace ibe {

namespace {
string const getEnv(char const* name) {
    char const* value = std::getenv(name);
    return value ? string(value) : string();
}

template <typename T>
T getEnv(char const* name, T def) {
    char const* value = std::getenv(name);
    if (value) {
        try {
            return boost::lexical_cast<T>(value);
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

HttpResponseCode const HttpResponseCode::OK(200, "OK", "The request has succeeded.");
HttpResponseCode const HttpResponseCode::BAD_REQUEST(
        400, "Bad Request",
        "The request could not be understood by the "
        "server due to malformed syntax.");
HttpResponseCode const HttpResponseCode::UNAUTHORIZED(
        401, "Unauthorized", "The request requires user authentication.");
HttpResponseCode const HttpResponseCode::FORBIDDEN(
        403, "Forbidden",
        "The server understood the request, but is "
        "refusing to fulfill it.");
HttpResponseCode const HttpResponseCode::NOT_FOUND(
        404, "Not Found",
        "The server has not found anything matching "
        "the Request-URI.");
HttpResponseCode const HttpResponseCode::NOT_ACCEPTABLE(
        406, "Not Acceptable",
        "The resource identified by the request is "
        "only capable of generating response entities which have content "
        "characteristics not acceptable according to the accept headers sent "
        "in the request.");
HttpResponseCode const HttpResponseCode::CONFLICT(
        409, "Conflict",
        "The request could not be completed due to a conflict "
        "with the current state of the resource.");
HttpResponseCode const HttpResponseCode::GONE(
        410, "Gone",
        "The requested resource is no longer available at the "
        "server and no forwarding address is known. ");
HttpResponseCode const HttpResponseCode::LENGTH_REQUIRED(
        411, "Length Required",
        "The server refuses to accept the request "
        "without a defined Content- Length.");
HttpResponseCode const HttpResponseCode::PRECONDITION_FAILED(
        412, "Precondition Failed",
        "The precondition given in one or more of "
        "the request-header fields evaluated to false when it was tested on the "
        "server.");
HttpResponseCode const HttpResponseCode::REQUEST_ENTITY_TOO_LARGE(
        413, "Request Entity Too Large",
        "The server is refusing to process a "
        "request because the request entity is larger than the server is willing "
        "or able to process.");
HttpResponseCode const HttpResponseCode::REQUEST_URI_TOO_LONG(
        414, "Request-URI Too Long",
        "The server is refusing to service the "
        "request because the Request-URI is longer than the server is willing "
        "to interpret.");
HttpResponseCode const HttpResponseCode::UNSUPPORTED_MEDIA_TYPE(
        415, "Unsupported Media Type",
        "The server is refusing to service the "
        "request because the entity of the request is in a format not supported "
        "by the requested resource for the requested method.");
HttpResponseCode const HttpResponseCode::INTERNAL_SERVER_ERROR(
        500, "Internal Server Error",
        "The server encountered an unexpected "
        "condition which prevented it from fulfilling the request.");
HttpResponseCode const HttpResponseCode::NOT_IMPLEMENTED(
        501, "Not Implemented",
        "The server does not support the functionality "
        "required to fulfill the request.");
HttpResponseCode const HttpResponseCode::BAD_GATEWAY(
        502, "Bad Gateway",
        "The server, while acting as a gateway or proxy, "
        "received an invalid response from the upstream server it accessed in "
        "attempting to fulfill the request.");
HttpResponseCode const HttpResponseCode::SERVICE_UNAVAILABLE(
        503, "Service Unavailable",
        "The server is currently unable to handle "
        "the request due to a temporary overloading "
        "or maintenance of the server.");
HttpResponseCode const HttpResponseCode::GATEWAY_TIMEOUT(
        504, "Gateway Timeout",
        "The server, while acting as a gateway or proxy, "
        "did not receive a timely response from the upstream server specified by "
        "the URI (e.g. HTTP, FTP, LDAP) or some other auxiliary server (e.g. DNS) "
        "it needed to access in attempting to complete the request.");
HttpResponseCode const HttpResponseCode::HTTP_VERSION_NOT_SUPPORTED(
        505, "HTTP Version Not Supported",
        "The server does not support, or "
        "refuses to support, the HTTP protocol version that was used in the "
        "request message.");

HttpResponseCode::HttpResponseCode(int code, char const* summary,
                                   char const* description)
        : _code(code), _summary(summary), _description(description) {}

HttpResponseCode::~HttpResponseCode() {}

// == HttpException implementation ----

/** Creates an HttpException from throw-site information.
 *
 * @param[in] file  Filename. Must be a compile-time string,
 *                  automatically passed in by HTTP_EXCEPT.
 * @param[in] line  Line number. Automatically passed in by HTTP_EXCEPT.
 * @param[in] func  Function name. Must be a compile-time string,
 *                  automatically passed in by HTTP_EXCEPT.
 * @param[in] msg   Informational string.
 */
HttpException::HttpException(char const* file, int line, char const* func,
                             HttpResponseCode const& code, string const& msg)
        : _file(file), _line(line), _func(func), _code(code), _msg(msg), _what() {}

HttpException::HttpException(char const* file, int line, char const* func,
                             HttpResponseCode const& code, char const* msg)
        : _file(file), _line(line), _func(func), _code(code), _msg(msg), _what() {}

HttpException::~HttpException() throw() {}

/** Writes a HTML representation of this exception to the given stream.
 *
 * @param[in] stream Reference to an output stream.
 * @return Reference to the output \c stream.
 */
void HttpException::writeErrorResponse(ostream& stream) const {
    int const c = _code.getCode();
    ostringstream oss;
    oss << "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.01//EN\" "
           "\"http://www.w3.org/TR/html4/strict.dtd\">\n"
           "<html>\n"
           "<head><title>"
        << c << " " << _code.getSummary()
        << "</title></head>\n"
           "<body>\n"
           "<h1>"
        << c << " " << _code.getSummary() << "</h1>\n"
        << _code.getDescription();
    // omit exception origin for 401, 403, 404 responses
    if (c != 401 && c != 403 && c != 404) {
        oss << "<br /><br />\n"
               "<tt>"
            << getTypeName() << "</tt> thrown at <tt>" << _file << ": " << _line
            << "</tt> in <tt>" << _func << "</tt>:<br/>\n"
            << _msg;
    }
    oss << "</body>\n"
           "</html>\n";
    string content = oss.str();
    stream << getEnv("SERVER_PROTOCOL") << " " << c << " " << _code.getSummary()
           << "\r\n"
              "Content-Language: en\r\n"
              "Content-Length: "
           << content.length()
           << "\r\n"
              "Content-Type: text/html; charset=utf-8\r\n"
              "Cache-Control: no-cache\r\n\r\n";
    stream << content;
    stream.flush();
}

/** Returns a character string representing this exception.  Falls back on
 * getTypeName() if an exception is thrown.
 *
 * @return String representation of this exception; must not be deleted.
 */
char const* HttpException::what() const throw() {
    try {
        return _msg.c_str();
    } catch (...) {
        return getTypeName();
    }
}

/** Returns the fully-qualified type name of the exception.  This must be
 * overridden by derived classes.
 *
 * @return Fully qualified exception type name; must not be deleted.
 */
char const* HttpException::getTypeName() const throw() { return "ibe::HttpException"; }

void writeErrorResponse(std::ostream& stream, std::exception const& e) {
    HttpResponseCode const& c = HttpResponseCode::INTERNAL_SERVER_ERROR;
    ostringstream oss;
    oss << "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.01//EN\" "
           "\"http://www.w3.org/TR/html4/strict.dtd\">\n"
           "<html>\n"
           "<head><title>"
        << c.getCode() << " " << c.getSummary()
        << "</title></head>\n"
           "<body>\n"
           "<h1>"
        << c.getCode() << " " << c.getSummary() << "</h1>\n"
        << c.getDescription()
        << "<br /><br />\n"
           "Caught <tt>std::exception</tt>:<br/>\n"
        << e.what()
        << "</body>\n"
           "</html>\n";
    string content = oss.str();
    stream << getEnv("SERVER_PROTOCOL") << " " << c.getCode() << " " << c.getSummary()
           << "\r\n"
              "Content-Language: en\r\n"
              "Content-Length: "
           << content.length()
           << "\r\n"
              "Content-Type: text/html; charset=utf-8\r\n"
              "Cache-Control: no-cache\r\n\r\n";
    stream << content;
    stream.flush();
}

void writeErrorResponse(std::ostream& stream) {
    HttpResponseCode const& c = HttpResponseCode::INTERNAL_SERVER_ERROR;
    ostringstream oss;
    oss << "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.01//EN\" "
           "\"http://www.w3.org/TR/html4/strict.dtd\">\n"
           "<html>\n"
           "<head><title>"
        << c.getCode() << " " << c.getSummary()
        << "</title></head>\n"
           "<body>\n"
           "<h1>"
        << c.getCode() << " " << c.getSummary() << "</h1>\n"
        << c.getDescription()
        << "<br /><br />\n"
           "Unexpected exception.\n"
           "</body>\n"
           "</html>\n";
    string content = oss.str();
    stream << getEnv("SERVER_PROTOCOL") << " " << c.getCode() << " " << c.getSummary()
           << "\r\n"
              "Content-Language: en\r\n"
              "Content-Length: "
           << content.length()
           << "\r\n"
              "Content-Type: text/html; charset=utf-8\r\n"
              "Cache-Control: no-cache\r\n\r\n";
    stream << content;
    stream.flush();
}

/** Returns a formatted string obtained by passing @c fmt and any trailing
 * arguments to the C @c vsnprintf function.
 */
string const format(char const* fmt, ...) {
    static string const FAILED = "Failed to format message";
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
            boost::scoped_array<char> bigbuf(new char[n + 1]);
            va_end(list);
            va_start(list, fmt);
            if (::vsnprintf(bigbuf.get(), static_cast<size_t>(n + 1), fmt, list) >= 0) {
                return string(bigbuf.get());
            }
        } else if (n >= 0) {
            return string(buf);
        }
    } catch (...) {
    }
    return FAILED;
}

// == Environment implementation ----

Environment::Environment(int argc, char const* const* argv)
        : _contentLength(getEnv<size_t>("CONTENT_LENGTH", 0)),
          _serverPort(getEnv<uint16_t>("SERVER_PORT", 0)),
          _isHTTPS(getEnv("HTTPS") == "on"),
          _serverName(getEnv("SERVER_NAME")),
          _gatewayInterface(getEnv("GATEWAY_INTERFACE")),
          _serverProtocol(getEnv("SERVER_PROTOCOL")),
          _requestMethod(getEnv("REQUEST_METHOD")),
          _pathInfo(getEnv("PATH_INFO")),
          _pathTranslated(getEnv("PATH_TRANSLATED")),
          _scriptName(getEnv("SCRIPT_NAME")),
          _queryString(getEnv("QUERY_STRING")),
          _contentType(getEnv("CONTENT_TYPE")),
          _cookieString(getEnv("HTTP_COOKIE")),
          _kvMap(),
          _cookieMap() {
    if (_contentType.empty() || _contentType == "application/x-www-form-urlencoded") {
        parseInput(_queryString);
    } else if (_contentType.compare(0, 19, "multipart/form-data") == 0) {
        if (_contentLength == 0) {
            throw HTTP_EXCEPT(HttpResponseCode::LENGTH_REQUIRED,
                              "Content-Length is missing, 0 or invalid.");
        } else if (_contentLength > 65535) {
            throw HTTP_EXCEPT(HttpResponseCode::REQUEST_ENTITY_TOO_LARGE,
                              "Content-Length too large (file uploads not supported).");
        }
        char postData[65536];
        cin.read(postData, _contentLength);
        parsePostInput(string(postData, cin.gcount()));
    } else if (argc > 0 && argv != 0) {
        parseInput(string(argv[0]));
    } else {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                          "Invalid Request-Method and/or Content-Type.");
    }
    parseCookies(_cookieString);
}

Environment::~Environment() {}

/** Returns a vector of all the query parameter names.
 */
vector<string> const Environment::getKeys() const {
    vector<string> keys;
    keys.reserve(_kvMap.size());
    KeyValueIter i = _kvMap.begin();
    KeyValueIter const e = _kvMap.end();
    for (; i != e; ++i) {
        if (keys.size() == 0 || keys.back() != i->first) {
            keys.push_back(i->first);
        }
    }
    return keys;
}

/** Returns the first value of the query parameter with the given name.
 */
string const& Environment::getValue(string const& key) const {
    size_t n = getNumValues(key);
    if (n == 0) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                          format("No value specified for parameter %s", key.c_str()));
    } else if (n > 1) {
        throw HTTP_EXCEPT(
                HttpResponseCode::BAD_REQUEST,
                format("Multiple values specified for parameter %s", key.c_str()));
    }
    return _kvMap.find(key)->second;
}

/** Returns the first value of the query parameter with the given name, or
 * the specified default if the parameter is unavailable.
 */
string const Environment::getValue(string const& key, string const& def) const {
    size_t n = getNumValues(key);
    if (n == 0) {
        return def;
    } else if (n > 1) {
        throw HTTP_EXCEPT(
                HttpResponseCode::BAD_REQUEST,
                format("Multiple values specified for parameter %s", key.c_str()));
    }
    return _kvMap.find(key)->second;
}

/** Returns the vector of values associated with the query parameter
 * of the given name.
 */
vector<string> const Environment::getValues(string const& key) const {
    vector<string> values;
    pair<KeyValueIter, KeyValueIter> const range = _kvMap.equal_range(key);
    for (KeyValueIter i = range.first; i != range.second; ++i) {
        values.push_back(i->second);
    }
    return values;
}

/** Returns a vector of all the cookie names.
 */
vector<string> const Environment::getCookieNames() const {
    vector<string> names;
    names.reserve(_cookieMap.size());
    for (CookieIter i = _cookieMap.begin(), e = _cookieMap.end(); i != e; ++i) {
        names.push_back(i->first);
    }
    return names;
}

/** Returns the value of the cookie with the given name.
 */
string const& Environment::getCookie(string const& name) const {
    CookieIter i = _cookieMap.find(name);
    if (i == _cookieMap.end()) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          format("No cookie named %s", name.c_str()));
    }
    return i->second;
}

/** Returns the value of the cookie with the given name, or the specified
 * default if no such cookie is available.
 */
string const Environment::getCookie(string const& name, string const& def) const {
    CookieIter i = _cookieMap.find(name);
    return (i == _cookieMap.end()) ? def : i->second;
}

/** Returns a vector of all cookie (name, value) pairs sent along with the
 * request.
 */
std::vector<HttpCookie> const Environment::getCookies() const {
    vector<HttpCookie> cookies;
    cookies.reserve(_cookieMap.size());
    for (CookieIter i = _cookieMap.begin(), e = _cookieMap.end(); i != e; ++i) {
        cookies.push_back(HttpCookie(i->first, i->second));
    }
    return cookies;
}

string const Environment::urlDecode(string const& src) {
    string result;
    result.reserve(src.size());
    for (string::size_type i = 0, n = src.size(); i < n; ++i) {
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

void Environment::parseInput(string const& data) {
    if (data.empty()) {
        return;
    }
    string key, value;
    string::size_type prev = 0;

    while (true) {
        string::size_type i = data.find_first_of('=', prev);
        if (i == string::npos) {
            // no more key=value pairs
            break;
        }
        // decode key
        key = urlDecode(data.substr(prev, i - prev));
        prev = i + 1;
        i = data.find_first_of('&', prev);
        if (i == string::npos) {
            value = data.substr(prev);
        } else {
            value = data.substr(prev, i - prev);
        }
        /// Do not decode 'path' because it has already been decoded
        /// once by Apache.  Double-decoding causes encoded plus '+'
        /// characters to become spaces ' '.
        if (key != "path") {
            value = urlDecode(value);
        }
        _kvMap.insert(std::make_pair(key, value));
        if (i == string::npos) {
            break;
        }
        prev = i + 1;
    }
}

void Environment::parsePostInput(string const& data) {
    static string const boundary = "boundary=";
    static string const headEnd = "\r\n\r\n";
    static string const cd = "Content-Disposition: form-data; ";
    static string const name = "name=\"";
    static string const filename = "filename=\"";

    string::size_type end, j, i = _contentType.find(boundary);
    string sep = "\r\n--";
    if (i == string::npos) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                          "Content-Type missing boundary specification");
    }
    i += boundary.size();
    if (_contentType[i] == '"') {
        i += 1;
        j = _contentType.find_first_of('"', i);
        if (j == string::npos) {
            throw HTTP_EXCEPT(
                    HttpResponseCode::BAD_REQUEST,
                    "Missing ending quote in Content-Type boundary specification");
        }
    } else {
        j = _contentType.find_first_of(';', i);
    }
    sep.append(_contentType, i, j - i);
    if (sep.size() > 74) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                          "Content-Type boundary specification too long");
    }
    end = data.rfind(sep);
    i = data.find(sep);
    while (i != string::npos) {
        i += sep.size();
        j = data.find(sep, i);
        if (j == string::npos) {
            break;
        }
        // Found a part that spans i to j
        string::size_type h = data.find(headEnd, i);
        if (h == string::npos) {
            throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                              "Malformed multipart/form-data header");
        }
        h += headEnd.size();
        // value spans [h, j). Parse Content-Disposition in header
        string::size_type nb = data.find(cd, i);
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
        string::size_type ne = data.find_first_of('"', nb);
        if (ne >= h) {
            throw HTTP_EXCEPT(
                    HttpResponseCode::BAD_REQUEST,
                    "Malformed multipart/form-data header: "
                    "Content-Disposition name parameter missing ending quote");
        }
        _kvMap.insert(std::make_pair(data.substr(nb, ne - nb), data.substr(h, j - h)));
        i = j + sep.size();
        if (i < data.size() - 2 && data[i] == '-' && data[i + 1] == '-') {
            // found multipart epilogue separator
            break;
        }
    }
}

void Environment::parseCookies(string const& data) {
    for (string::size_type i = 0, j = 0; j != string::npos; i = j + 1) {
        j = data.find(";", i);
        string::size_type sep = data.find("=", i);
        if (sep != string::npos && sep < j) {
            // eat whitespace
            for (; std::isspace(data[i]) != 0; ++i) {
            }
            if (i != sep) {
                if (j == string::npos) {
                    _cookieMap.insert(std::make_pair(data.substr(i, sep - i),
                                                     data.substr(sep + 1)));
                } else {
                    _cookieMap.insert(
                            std::make_pair(data.substr(i, sep - i),
                                           data.substr(sep + 1, j - sep - 1)));
                }
            }
        }
    }
}

// == Writer implementation ----

Writer::~Writer() {}

// == ChunkedWriter implementation ----

ChunkedWriter::~ChunkedWriter() {}

void ChunkedWriter::write(unsigned char const* const buf, size_t const len) {
    if (buf == 0 || len == 0) {
        return;
    }
    if (std::printf("%llX\r\n", static_cast<unsigned long long>(len)) < 0) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "failed to write to standard out");
    }
    if (std::fwrite(buf, len, 1, ::stdout) != 1) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "failed to write to standard out");
    }
    if (std::fwrite("\r\n", 2, 1, ::stdout) != 1) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "failed to write to standard out");
    }
}

void ChunkedWriter::finish() {
    if (std::fwrite("0\r\n\r\n", 5, 1, ::stdout) != 1) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "failed to write to standard out");
    }
    std::fflush(::stdout);
}

// == MemoryWriter implementation ---

MemoryWriter::MemoryWriter() : _contentLength(0), _cap(1024 * 1024), _content(0) {
    _content = (unsigned char*)std::malloc(_cap);
    if (_content == 0) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "memory allocation failed");
    }
}

MemoryWriter::~MemoryWriter() { std::free(_content); }

void MemoryWriter::write(unsigned char const* const buf, size_t const len) {
    if (_contentLength + len < _contentLength) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "too much data to buffer in memory");
    } else if (_contentLength + len > _cap) {
        size_t nc = std::max(2 * _cap, _contentLength + len);
        unsigned char* c = (unsigned char*)std::realloc(_content, nc);
        if (c == 0) {
            throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                              "memory reallocation failed");
        }
        _content = c;
        _cap = nc;
    }
    std::memcpy(_content + _contentLength, buf, len);
    _contentLength += len;
}

void MemoryWriter::finish() {}

// == GZIPWriter implementation ----

GZIPWriter::GZIPWriter(Writer& writer, size_t const chunkSize)
        : _writer(&writer), _chunkSize(chunkSize), _stream(), _buffer() {
    boost::scoped_array<unsigned char> mem(new unsigned char[chunkSize]);
    // setup zlib (15 window bits, add 16 to indicate a gzip compatible header is
    // desired)
    if (::deflateInit2(&_stream, 1, Z_DEFLATED, MAX_WBITS + 16, MAX_MEM_LEVEL,
                       Z_DEFAULT_STRATEGY) != Z_OK) {
        throw HTTP_EXCEPT(
                HttpResponseCode::INTERNAL_SERVER_ERROR,
                "[zlib] deflateInit2() failed to initialize compression stream");
    }
    swap(_buffer, mem);
    _stream.next_out = _buffer.get();
    _stream.avail_out = _chunkSize;
}

GZIPWriter::~GZIPWriter() { ::deflateEnd(&_stream); }

void GZIPWriter::write(unsigned char const* const buf, size_t const len) {
    if (buf == 0 || len == 0) {
        return;
    }
    _stream.next_in = const_cast<Bytef*>(buf);
    _stream.avail_in = len;
    // deflate/write until the buffer passed in by the user has been consumed
    do {
        int const zret = ::deflate(&_stream, Z_NO_FLUSH);
        if (zret != Z_OK) {
            throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                              format("[zlib] deflate() failed, return code: %d", zret));
        }
        if (_stream.avail_out != 0) {
            if (_stream.avail_in != 0) {
                throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                                  "[zlib] deflate() failed to consume input");
            }
            break;
        }
        // no more space left in _buffer, write it out
        _writer->write(_buffer.get(), _chunkSize);
        _stream.next_out = _buffer.get();
        _stream.avail_out = _chunkSize;
    } while (_stream.avail_in != 0);
}

void GZIPWriter::finish() {
    if (_stream.avail_out == 0) {
        _writer->write(_buffer.get(), _chunkSize);
        _stream.next_out = _buffer.get();
        _stream.avail_out = _chunkSize;
    }
    while (true) {
        int const zret = ::deflate(&_stream, Z_FINISH);
        if (zret == Z_STREAM_END) {
            _writer->write(_buffer.get(), _chunkSize - _stream.avail_out);
            break;
        } else if (zret == Z_OK) {
            if (_stream.avail_out != 0) {
                throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                                  "[zlib] deflate() failed to fill output buffer");
            }
            _writer->write(_buffer.get(), _chunkSize);
            _stream.next_out = _buffer.get();
            _stream.avail_out = _chunkSize;
        } else {
            throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                              format("[zlib] deflate() failed, return code: %d", zret));
        }
    }
    _writer->finish();
}

}  // namespace ibe
