#include "write_error_response.hxx"

// Standard library
#include <sstream>
#include <string>

// Local headers
#include "HttpResponseCode.hxx"
#include "get_env.hxx"

namespace ibe {
void write_error_response(std::ostream& stream, std::exception const& e) {
    HttpResponseCode const& c = HttpResponseCode::INTERNAL_SERVER_ERROR;
    std::ostringstream oss;
    oss << "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.01//EN\" "
           "\"http://www.w3.org/TR/html4/strict.dtd\">\n"
           "<html>\n"
           "<head><title>"
        << c.get_code() << " " << c.get_summary()
        << "</title></head>\n"
           "<body>\n"
           "<h1>"
        << c.get_code() << " " << c.get_summary() << "</h1>\n"
        << c.get_description()
        << "<br /><br />\n"
           "Caught <tt>std::exception</tt>:<br/>\n"
        << e.what()
        << "</body>\n"
           "</html>\n";
    std::string content = oss.str();
    stream << get_env("SERVER_PROTOCOL") << " " << c.get_code() << " "
           << c.get_summary()
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

void write_error_response(std::ostream& stream) {
    HttpResponseCode const& c = HttpResponseCode::INTERNAL_SERVER_ERROR;
    std::ostringstream oss;
    oss << "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.01//EN\" "
           "\"http://www.w3.org/TR/html4/strict.dtd\">\n"
           "<html>\n"
           "<head><title>"
        << c.get_code() << " " << c.get_summary()
        << "</title></head>\n"
           "<body>\n"
           "<h1>"
        << c.get_code() << " " << c.get_summary() << "</h1>\n"
        << c.get_description()
        << "<br /><br />\n"
           "Unexpected exception.\n"
           "</body>\n"
           "</html>\n";
    std::string content = oss.str();
    stream << get_env("SERVER_PROTOCOL") << " " << c.get_code() << " "
           << c.get_summary()
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
}  // namespace ibe
