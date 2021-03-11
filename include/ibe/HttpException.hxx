#pragma once

// Standard library
#include <exception>
#include <string>

// local headers
#include "HttpResponseCode.hxx"

#if defined(__cplusplus) && __cplusplus >= 201103
#define EXCEPT_HERE __FILE__, __LINE__, __func__
#elif defined(IBE_USE_BOOST)
#define EXCEPT_HERE __FILE__, __LINE__, BOOST_CURRENT_FUNCTION
#else
#define EXCEPT_HERE __FILE__, __LINE__, "(unknown)"
#endif

/** Creates an HttpException with the given response code and
 * informational message.
 *
 * @param[in] code   An HttpResponseCode.
 * @param[in] msg    Informational message.
 */
#define HTTP_EXCEPT(...) ::ibe::HttpException(EXCEPT_HERE, __VA_ARGS__)

namespace ibe {
/** An Exception class with an associated HTTP response code.
 */
class HttpException : public std::exception {
public:
    HttpException(char const* file, int line, char const* func,
                  HttpResponseCode const& code, std::string const& msg);
    HttpException(char const* file, int line, char const* func,
                  HttpResponseCode const& code, char const* msg = "");
    virtual ~HttpException() throw();

    virtual void write_error_response(std::ostream& stream) const;
    virtual char const* what() const throw();
    virtual char const* get_type_name() const throw();

    char const* get_file() const throw() { return file_; }
    int get_line() const throw() { return line_; }
    char const* get_function() const throw() { return func_; }
    HttpResponseCode const& get_response_code() const throw() { return code_; }
    std::string const& get_message() const throw() { return msg_; }

private:
    char const* file_;
    int line_;
    char const* func_;
    HttpResponseCode const& code_;
    std::string msg_;
    mutable std::string what_;
};
}  // namespace ibe
