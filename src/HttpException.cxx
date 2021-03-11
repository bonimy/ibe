#include "HttpException.hxx"

// Standard library
#include <cstdlib>
#include <sstream>

// Local headers
#include "get_env.hxx"

namespace ibe {
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
                             HttpResponseCode const& code, std::string const& msg)
        : file_(file), line_(line), func_(func), code_(code), msg_(msg), what_() {}

HttpException::HttpException(char const* file, int line, char const* func,
                             HttpResponseCode const& code, char const* msg)
        : file_(file), line_(line), func_(func), code_(code), msg_(msg), what_() {}

HttpException::~HttpException() throw() {}

/** Writes a HTML representation of this exception to the given stream.
 *
 * @param[in] stream Reference to an output stream.
 * @return Reference to the output \c stream.
 */
void HttpException::write_error_response(std::ostream& stream) const {
    int const c = code_.get_code();
    std::ostringstream oss;
    oss << "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.01//EN\" "
           "\"http://www.w3.org/TR/html4/strict.dtd\">\n"
           "<html>\n"
           "<head><title>"
        << c << " " << code_.get_summary()
        << "</title></head>\n"
           "<body>\n"
           "<h1>"
        << c << " " << code_.get_summary() << "</h1>\n"
        << code_.get_description();

    // omit exception origin for 401, 403, 404 responses
    if (c != 401 && c != 403 && c != 404) {
        oss << "<br /><br />\n"
               "<tt>"
            << get_type_name() << "</tt> thrown at <tt>" << file_ << ": " << line_
            << "</tt> in <tt>" << func_ << "</tt>:<br/>\n"
            << msg_;
    }
    oss << "</body>\n"
           "</html>\n";
    std::string content = oss.str();
    stream << get_env("SERVER_PROTOCOL") << " " << c << " " << code_.get_summary()
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
        return msg_.c_str();
    } catch (...) {
        return get_type_name();
    }
}

/** Returns the fully-qualified type name of the exception.  This must be
 * overridden by derived classes.
 *
 * @return Fully qualified exception type name; must not be deleted.
 */
char const* HttpException::get_type_name() const throw() {
    return "ibe::HttpException";
}
}  // namespace ibe
