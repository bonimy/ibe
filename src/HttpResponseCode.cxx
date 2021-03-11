#include "HttpResponseCode.hxx"

namespace ibe {
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
        : code_(code), summary_(summary), description_(description) {}

HttpResponseCode::~HttpResponseCode() {}
}  // namespace ibe
