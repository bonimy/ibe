#pragma once

// Local headers
#include "HttpCookie.hxx"

// Standard library
#include <map>
#include <string>
#include <vector>

namespace ibe {
/** Class encapsulating the CGI environment of a request.
 */
class Environment {
public:
    Environment(int argc = 0, char const* const* argv = 0);
    ~Environment();

    /// \name Server environment
    //@{
    /// Returns the host name or IP address of the HTTP server.
    std::string const& get_server_name_() const { return server_name_; }

    /// Returns the name and version of the gateway interface (usually @c
    /// CGI/1.1).
    std::string const& get_gateway_interface() const { return gateway_interface_; }

    /// Returns the name and version of the protocol (usually @c HTTP/1.0 or @c
    /// HTTP/1.1).
    std::string const& get_server_protocol() const { return server_protocol_; }

    /// Returns the HTTP server port number.
    uint16_t get_server_port() const { return server_port_; }

    /// Returns @c true if this is an HTTPS request.
    bool is_https() const { return is_https_; }

    //@}

    /// \name CGI environment
    //@{
    /// Returns the request method, usually @c GET or @c POST.
    std::string const& get_request_method() const { return request_method_; }

    /// Returns path information for this request.
    std::string const& get_path_info() const { return path_info_; }

    /// Returns translated path information for this request.
    std::string const& get_path_translated() const { return path_translated_; }

    /// Returns the full path to this CGI application.
    std::string const& get_script_name() const { return script_name_; }

    /// Returns the query string for the request; usually only valid for a @c
    /// GET.
    std::string const& get_query_string() const { return query_string_; }

    /// Returns the number of characters to read from standard input; usually
    /// only valid for a @c POST.
    size_t get_content_length() const { return content_length_; }

    /// Returns the MIME type of the content submitted by a @c POST; usually
    /// @c application/x-www-form-urlencoded.
    std::string const& get_content_type() const { return content_type_; }

    /// Returns the cookies sent along with the request.
    std::string const& get_cookie_string() const { return cookie_string_; }

    //@}

    /// \name CGI Parameters
    //@{
    /// Returns the total number of query parameter values.
    size_t get_num_values() const { return kv_map_.size(); }

    /// Returns the number of values for the query parameter with the given name.
    size_t get_num_values(std::string const& key) const { return kv_map_.count(key); }

    /// Returns @c true if a query parameter with the given name exists.
    bool hasKey(std::string const& key) const { return get_num_values(key) != 0; }
    std::vector<std::string> const get_keys() const;
    std::string const& get_value(std::string const& key) const;
    std::string get_value_or_default(std::string const& key,
                                     std::string const& def) const;
    std::vector<std::string> const get_values(std::string const& key) const;

    //@}

    /// \name Cookies
    //@{
    /// Returns the total number of cookies.
    size_t get_num_cookies() const { return cookie_map_.size(); }

    /// Returns @c true if a cookie with the given name exists.
    bool has_cookie(std::string const& name) const {
        return cookie_map_.count(name) != 0;
    }
    std::vector<std::string> const get_cookie_names() const;
    std::string const& get_cookie(std::string const& name) const;
    std::string const get_cookie(std::string const& name, std::string const& def) const;
    std::vector<HttpCookie> const get_cookies() const;

    //@}

    /// \name Utilities
    static std::string const url_decode(std::string const& src);

    //@}

private:
    typedef std::multimap<std::string, std::string> KeyValueMap;
    typedef KeyValueMap::const_iterator KeyValueIter;
    typedef std::map<std::string, std::string> CookieMap;
    typedef CookieMap::const_iterator CookieIter;

    // Disable copying and assignment
    Environment(Environment const&) = delete;
    Environment& operator=(Environment const&) = delete;

    void parse_input(std::string const& data);
    void parse_post_input(std::string const& data);
    void parse_cookies(std::string const& data);

    size_t content_length_;
    uint16_t server_port_;
    bool is_https_;

    std::string server_name_;
    std::string gateway_interface_;
    std::string server_protocol_;
    std::string request_method_;
    std::string path_info_;
    std::string path_translated_;
    std::string script_name_;
    std::string query_string_;
    std::string content_type_;
    std::string cookie_string_;

    KeyValueMap kv_map_;
    CookieMap cookie_map_;
};
}  // namespace ibe
