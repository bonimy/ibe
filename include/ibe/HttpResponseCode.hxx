#pragma once

namespace ibe {
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

    int get_code() const { return code_; }
    char const* get_summary() const { return summary_; }
    char const* get_description() const { return description_; }

private:
    HttpResponseCode(int code, char const* summary, char const* description);

    // disable copy construction and assignment
    HttpResponseCode(HttpResponseCode const&) = delete;
    HttpResponseCode& operator=(HttpResponseCode const&) = delete;

    int code_;
    char const* summary_;
    char const* description_;
};
}  // namespace ibe
