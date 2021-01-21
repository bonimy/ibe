/** @file
 * @brief  Minimalistic CGI request handling library.
 * @author Serge Monkewitz
 */
#pragma once

#include <stdint.h>
#include <zlib.h>
#if ZLIB_VERNUM < 0x123
#warning Older version of zlib detected, upgrading to version 1.2.3 or later is recommended
#endif

#include <cstdarg>
#include <exception>
#include <iosfwd>
#include <map>
#include <string>
#include <vector>

#include "boost/current_function.hpp"
#include "boost/scoped_array.hpp"

namespace ibe {

#define EXCEPT_HERE __FILE__, __LINE__, BOOST_CURRENT_FUNCTION

/** Creates an HttpException with the given response code and
 * informational message.
 *
 * @param[in] code   An HttpResponseCode.
 * @param[in] msg    Informational message.
 */
#define HTTP_EXCEPT(...) ::ibe::HttpException(EXCEPT_HERE, __VA_ARGS__)

/** A subset of the available HTTP response codes (those most likely to be
 * useful from a CGI application).
 */
class HttpResponseCode {
public:
    static HttpResponseCode const OK;
    static HttpResponseCode const BAD_REQUEST;
    static HttpResponseCode const UNAUTHORIZED;
    static HttpResponseCode const FORBIDDEN;
    static HttpResponseCode const NOT_FOUND;
    static HttpResponseCode const NOT_ACCEPTABLE;
    static HttpResponseCode const CONFLICT;
    static HttpResponseCode const GONE;
    static HttpResponseCode const LENGTH_REQUIRED;
    static HttpResponseCode const PRECONDITION_FAILED;
    static HttpResponseCode const REQUEST_ENTITY_TOO_LARGE;
    static HttpResponseCode const REQUEST_URI_TOO_LONG;
    static HttpResponseCode const UNSUPPORTED_MEDIA_TYPE;
    static HttpResponseCode const INTERNAL_SERVER_ERROR;
    static HttpResponseCode const NOT_IMPLEMENTED;
    static HttpResponseCode const BAD_GATEWAY;
    static HttpResponseCode const SERVICE_UNAVAILABLE;
    static HttpResponseCode const GATEWAY_TIMEOUT;
    static HttpResponseCode const HTTP_VERSION_NOT_SUPPORTED;

    ~HttpResponseCode();

    int getCode() const { return _code; }
    char const* getSummary() const { return _summary; }
    char const* getDescription() const { return _description; }

private:
    HttpResponseCode(int code, char const* summary, char const* description);
    // disable copy construction and assignment
    HttpResponseCode(HttpResponseCode const&);
    HttpResponseCode& operator=(HttpResponseCode const&);

    int _code;
    char const* _summary;
    char const* _description;
};

/** An Exception class with an associated HTTP response code.
 */
class HttpException : public std::exception {
public:
    HttpException(char const* file, int line, char const* func,
                  HttpResponseCode const& code, std::string const& msg);
    HttpException(char const* file, int line, char const* func,
                  HttpResponseCode const& code, char const* msg = "");
    virtual ~HttpException() throw();

    virtual void writeErrorResponse(std::ostream& stream) const;
    virtual char const* what() const throw();
    virtual char const* getTypeName() const throw();

    char const* getFile() const throw() { return _file; }
    int getLine() const throw() { return _line; }
    char const* getFunction() const throw() { return _func; }
    HttpResponseCode const& getResponseCode() const throw() { return _code; }
    std::string const& getMessage() const throw() { return _msg; }

private:
    char const* _file;
    int _line;
    char const* _func;
    HttpResponseCode const& _code;
    std::string _msg;
    mutable std::string _what;
};

void writeErrorResponse(std::ostream& stream, std::exception const& e);
void writeErrorResponse(std::ostream& stream);
std::string const format(char const* fmt, ...);

/** A name value pair.
 */
typedef std::pair<std::string, std::string> HttpCookie;

/** Class encapsulating the CGI environment of a request.
 */
class Environment {
public:
    Environment(int argc = 0, char const* const* argv = 0);
    ~Environment();

    /// \name Server environment
    //@{
    /// Returns the host name or IP address of the HTTP server.
    std::string const& getServerName() const { return _serverName; }
    /// Returns the name and version of the gateway interface (usually @c
    /// CGI/1.1).
    std::string const& getGatewayInterface() const { return _gatewayInterface; }
    /// Returns the name and version of the protocol (usually @c HTTP/1.0 or @c
    /// HTTP/1.1).
    std::string const& getServerProtocol() const { return _serverProtocol; }
    /// Returns the HTTP server port number.
    uint16_t getServerPort() const { return _serverPort; }
    /// Returns @c true if this is an HTTPS request.
    bool isHTTPS() const { return _isHTTPS; }
    //@}

    /// \name CGI environment
    //@{
    /// Returns the request method, usually @c GET or @c POST.
    std::string const& getRequestMethod() const { return _requestMethod; }
    /// Returns path information for this request.
    std::string const& getPathInfo() const { return _pathInfo; }
    /// Returns translated path information for this request.
    std::string const& getPathTranslated() const { return _pathTranslated; }
    /// Returns the full path to this CGI application.
    std::string const& getScriptName() const { return _scriptName; }
    /// Returns the query string for the request; usually only valid for a @c
    /// GET.
    std::string const& getQueryString() const { return _queryString; }
    /// Returns the number of characters to read from standard input; usually
    /// only valid for a @c POST.
    size_t getContentLength() const { return _contentLength; }
    /// Returns the MIME type of the content submitted by a @c POST; usually
    /// @c application/x-www-form-urlencoded.
    std::string const& getContentType() const { return _contentType; }
    /// Returns the cookies sent along with the request.
    std::string const& getCookieString() const { return _cookieString; }
    //@}

    /// \name CGI Parameters
    //@{
    /// Returns the total number of query parameter values.
    size_t getNumValues() const { return _kvMap.size(); }
    /// Returns the number of values for the query parameter with the given name.
    size_t getNumValues(std::string const& key) const { return _kvMap.count(key); }
    /// Returns @c true if a query parameter with the given name exists.
    bool hasKey(std::string const& key) const { return getNumValues(key) != 0; }
    std::vector<std::string> const getKeys() const;
    std::string const& getValue(std::string const& key) const;
    std::string const getValue(std::string const& key, std::string const& def) const;
    std::vector<std::string> const getValues(std::string const& key) const;
    //@}

    /// \name Cookies
    //@{
    /// Returns the total number of cookies.
    size_t getNumCookies() const { return _cookieMap.size(); }
    /// Returns @c true if a cookie with the given name exists.
    bool hasCookie(std::string const& name) const {
        return _cookieMap.count(name) != 0;
    }
    std::vector<std::string> const getCookieNames() const;
    std::string const& getCookie(std::string const& name) const;
    std::string const getCookie(std::string const& name, std::string const& def) const;
    std::vector<HttpCookie> const getCookies() const;
    //@}

    /// \name Utilities
    static std::string const urlDecode(std::string const& src);
    //@}

private:
    typedef std::multimap<std::string, std::string> KeyValueMap;
    typedef KeyValueMap::const_iterator KeyValueIter;
    typedef std::map<std::string, std::string> CookieMap;
    typedef CookieMap::const_iterator CookieIter;

    // Disable copying and assignment
    Environment(Environment const&);
    Environment& operator=(Environment const&);

    void parseInput(std::string const& data);
    void parsePostInput(std::string const& data);
    void parseCookies(std::string const& data);

    size_t _contentLength;
    uint16_t _serverPort;
    bool _isHTTPS;

    std::string _serverName;
    std::string _gatewayInterface;
    std::string _serverProtocol;
    std::string _requestMethod;
    std::string _pathInfo;
    std::string _pathTranslated;
    std::string _scriptName;
    std::string _queryString;
    std::string _contentType;
    std::string _cookieString;

    KeyValueMap _kvMap;
    CookieMap _cookieMap;
};

/** Base class for output writers.
 */
class Writer {
public:
    virtual ~Writer();

    virtual void write(unsigned char const* const buf, size_t const len) = 0;
    virtual void finish() = 0;
};

/** Writes chunked output to standard out.
 */
class ChunkedWriter : public Writer {
public:
    ChunkedWriter() {}
    virtual ~ChunkedWriter();

    virtual void write(unsigned char const* const buf, size_t const len);
    virtual void finish();

private:
    // disable copy construction and assignment
    ChunkedWriter(ChunkedWriter const&);
    ChunkedWriter& operator=(ChunkedWriter const&);
};

/** Writes output to an in-memory buffer.
 */
class MemoryWriter : public Writer {
public:
    MemoryWriter();
    virtual ~MemoryWriter();

    virtual void write(unsigned char const* const buf, size_t const len);
    virtual void finish();
    size_t getContentLength() const { return _contentLength; }
    unsigned char const* getContent() const { return _content; }

private:
    // disable copy construction and assignment
    MemoryWriter(MemoryWriter const&);
    MemoryWriter& operator=(MemoryWriter const&);

    size_t _contentLength;
    size_t _cap;
    unsigned char* _content;
};

/** Writes chunked, GZIP compressed output to another writer.
 */
class GZIPWriter : public Writer {
public:
    explicit GZIPWriter(Writer& writer, size_t const chunkSize = 8192);
    virtual ~GZIPWriter();

    virtual void write(unsigned char const* const buf, size_t const size);
    virtual void finish();

    size_t getChunkSize() const { return _chunkSize; }

private:
    // disable copy construction and assignment
    GZIPWriter(GZIPWriter const&);
    GZIPWriter& operator=(GZIPWriter const&);

    Writer* _writer;
    size_t const _chunkSize;                     ///< output granularity
    z_stream _stream;                            ///< zlib state
    boost::scoped_array<unsigned char> _buffer;  ///< compressed output buffer
};

}  // namespace ibe
