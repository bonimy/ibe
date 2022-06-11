// Local headers
#include "Access.hxx"
#include "Coords.hxx"
#include "GZIPWriter.hxx"
#include "HttpException.hxx"
#include "HttpResponseCode.hxx"
#include "MemoryWriter.hxx"
#include "check_access.hxx"
#include "format.hxx"
#include "ibe_filesystem.hxx"
#include "parse_coords.hxx"
#include "stream_subimage.hxx"
#include "write_error_response.hxx"

// Standard library
#include <cstdio>
#include <iostream>
#include <memory>
#include <regex>
#include <set>
#include <sstream>
#include <utility>

using std::make_pair;
using std::pair;
using std::set;
using std::string;
using std::vector;

namespace fs = ibe::fs;

using ibe::Access;
using ibe::Coords;
using ibe::DEG;
using ibe::Environment;
using ibe::format;
using ibe::GZIPWriter;
using ibe::HttpException;
using ibe::HttpResponseCode;
using ibe::MemoryWriter;

namespace {
// Return a vector of (filename extension, MIME content-type) pairs.
vector<pair<string, string> > const get_content_types() {
    vector<pair<string, string> > v;
    v.push_back(make_pair(".zip", "application/zip"));
    v.push_back(make_pair(".gz .tgz", "application/gzip"));
    v.push_back(make_pair("fits", "application/fits"));
    v.push_back(make_pair(".gif", "image/gif"));
    v.push_back(make_pair(".jpg .jpeg", "image/jpeg"));
    v.push_back(make_pair(".png", "image/png"));
    v.push_back(make_pair(".htm .html", "text/html; charset=utf-8"));
    v.push_back(make_pair(".csv", "text/csv; charset=utf-8"));
    v.push_back(make_pair(".txt .text .tbl .md5 .anc", "text/plain; charset=utf-8"));
    return v;
}

string to_lower_copy(const string& str) {
    string result(str);
    std::transform(result.begin(), result.end(), result.begin(),
                   [](char c) -> char { return static_cast<char>(std::tolower(c)); });
    return result;
}

bool is_valid_path(const fs::path& path) {
    string path_string = path.generic_string();

    // References to the parent directory are not allowed for security reasons
    return path_string.find("..") == string::npos &&
           (path.empty() || path_string[0] != '/');
}

bool is_valid_prefix(const fs::path& prefix) {
    string prefix_string = prefix.generic_string();
    size_t last = prefix_string.size() - 1;

    // References to the parent directory are not allowed for security reasons
    return prefix_string.find("..") == string::npos &&
           (prefix.empty() || (prefix_string[0] != '/' && prefix_string[last] == '/'));
}

bool is_valid_url_root(const fs::path& url_root) {
    string url_root_string = url_root.generic_string();

    // References to the parent directory are not allowed for security reasons
    return !url_root.empty() && url_root_string.find("..") == string::npos &&
           url_root_string[0] == '/';
}

// Perform basic sanity checking of the CGI environment, including common query
// parameters.
void validate(ibe::Environment const& env) {
    if (env.get_server_protocol() != "HTTP/1.1" &&
        env.get_server_protocol() != "HTTP/1.0") {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                          "Invalid protocol: use either HTTP/1.0 or HTTP/1.1");
    }
    vector<string> keys = env.get_keys();
    set<string> allowed({"url_root", "policy", "mission", "group", "pgconn", "pgtable",
                         "path", "prefix", "center", "size", "gzip"});
    for (vector<string>::const_iterator i = keys.begin(), e = keys.end(); i != e; ++i) {
        if (allowed.count(*i) != 1) {
            throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                              format("unknown parameter: %s", i->c_str()));
        }
    }

    if (!is_valid_path(env.get_value_or_default("path", ""))) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST);
    }
    if (!is_valid_prefix(env.get_value_or_default("prefix", ""))) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST);
    }
    if (!is_valid_url_root(env.get_value_or_default("url_root", "/"))) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST);
    }
}

// Check that cutout parameters are/are not present.
void validate_cutout_params(ibe::Environment const& env, bool is_cutout) {
    size_t n = env.get_num_values("center");
    if (is_cutout && n != 1) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                          "center parameter must be specifed exactly once");
    } else if (!is_cutout && n != 0) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST, "invalid parameter: center");
    }
    n = env.get_num_values("size");
    if (is_cutout && n != 1) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                          "size parameter must be specifed exactly once");
    } else if (!is_cutout && n != 0) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST, "invalid parameter: size");
    }
    n = env.get_num_values("gzip");
    if (is_cutout && n > 1) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                          "gzip parameter must be specifed at most once");
    } else if (!is_cutout && n != 0) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST, "invalid parameter: gzip");
    }
}

// Return the boolean value of the given query parameter or defaultValue.
bool parse_bool(Environment const& env, string const& key, bool default_value) {
    static std::regex const true_regex("^\\s*(1|on?|y(es)?|t(rue)?)\\s*",
                                       std::regex::icase);
    static std::regex const false_regex("^\\s*(0|no?|o(ff?)?|f(alse)?)\\s*",
                                        std::regex::icase);
    if (!env.hasKey(key)) {
        return default_value;
    }

    string const value = env.get_value(key);
    if (std::regex_match(value, true_regex)) {
        return true;
    } else if (std::regex_match(value, false_regex)) {
        return false;
    }
    throw HTTP_EXCEPT(
            HttpResponseCode::BAD_REQUEST,
            format("Value of %s parameter must equal (case insensitively) one of"
                   "1,y[es],t[rue],on or 0,n[o],f[alse],off",
                   key.c_str()));
    return false;
}

// Return a directory listing obtained from the file system.
vector<string> const get_dir_entries(fs::path const& path) {
    vector<string> entries;
    for (fs::directory_iterator d = fs::directory_iterator(path),
                                e = fs::directory_iterator();
         d != e; ++d) {
        if (d->status().type() == fs::directory_file) {
            entries.push_back(d->path().filename().string() + "/");
        } else if (d->status().type() == fs::regular_file) {
            entries.push_back(d->path().filename().string());
        }
    }
    return entries;
}

// Return a directory listing.
//
// Note that path has the form <f_1>/<f_2>/.../<f_i>. The corresponding
// on-disk path is obtained by prefixing IBE_DATA_ROOT and <prefix>. The
// corresponding URL is obtained by prefixing url_root and <prefix>.
//
// The path name stored in the file system metadata database (if there is one)
// is <f_1>/<f_2>/.../<f_i>, where the empty string corresponds to the root
// directory.
string const get_dir_listing(const fs::path& path, Environment const& env,
                             Access const& access) {
    std::ostringstream oss;
    vector<string> entries;
    fs::path prefix(env.get_value_or_default("prefix", ""));
    fs::path diskpath = fs::path(IBE_DATA_ROOT) / prefix / path;
    if (access.get_policy() == Access::GRANTED && access.get_pg_conn().empty()) {
        entries = get_dir_entries(diskpath);
    } else if (access.get_policy() != Access::DENIED) {
        entries = get_dir_entries(diskpath, path, access);
    }

    // sort directory entries by name
    std::sort(entries.begin(), entries.end());

    // build HTML
    fs::path url_root(env.get_value_or_default("url_root", "/"));
    fs::path url = url_root / prefix / path;
    fs::path parent = url.parent_path();
    string a_prefix = url.filename().string();
    if (a_prefix == "." || path.empty()) {
        a_prefix.clear();
        parent = parent.parent_path();
    } else {
        a_prefix += "/";
    }
    oss << "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.01//EN\" "
           "\"http://www.w3.org/TR/html4/strict.dtd\">\n"
           "<html>\n"
           "<head>\n"
           "<title>Index of "
        << url.string() << "</title>\n"
        << "</head>\n"
           "<body>\n"
           "<h1>Index of "
        << url.string() << "</h1>\n"
        << "<ul>\n";
    if (!parent.empty()) {
        oss << "<li><a href=\"" << parent.string() << "/\">Parent Directory</a></li>\n";
    }
    for (vector<string>::const_iterator i = entries.begin(), e = entries.end(); i != e;
         ++i) {
        oss << "<li><a href=\"" << a_prefix << *i << "\">" << *i << "</a></li>\n";
    }
    oss << "</ul>\n"
           "</body>\n"
           "</html>";
    return oss.str();
}
}  // unnamed namespace

int serve_directory_listing(const fs::path& path, const Environment& env,
                            const Access& access, bool& sent_header) {
    validate_cutout_params(env, false);
    string listing = get_dir_listing(path, env, access);
    sent_header = true;

    // write HTTP header
    if (std::fprintf(stdout,
                     "%s 200 OK\r\n"
                     "Content-Type: text/html; charset=utf-8\r\n"
                     "Content-Length: %llu\r\n"
                     "\r\n",
                     env.get_server_protocol().c_str(),
                     static_cast<unsigned long long>(listing.size())) < 0) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "failed to write to standard out");
    }

    // send back data
    if (std::fwrite(listing.c_str(), listing.size(), 1, stdout) != 1) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "failed to write to standard out");
    }
    return 0;
}

int serve_fits_cutout(const fs::path& filename, const fs::path& diskpath,
                      const Environment& env, bool& sent_header) {
    // 2. Serve a FITS cutout
    validate_cutout_params(env, true);
    bool const isGzip = parse_bool(env, "gzip", true);
    Coords center = parse_coords(env, "center", DEG, true);
    Coords size = parse_coords(env, "size", DEG, false);

    // Use ChunkedWriter for HTTP 1.1? But then... no way
    // to come back with an error message when something fails in
    // the middle of a sub-image operation.
    MemoryWriter wr;
    if (isGzip) {
        GZIPWriter gzwr(wr);
        stream_subimage(diskpath, center, size, gzwr);
        gzwr.finish();
    } else {
        stream_subimage(diskpath, center, size, wr);
        wr.finish();
    }

    // send back header
    sent_header = true;
    if (std::fprintf(stdout,
                     "%s 200 OK\r\n"
                     "Content-Type: %s\r\n"
                     "Content-Disposition: attachment; filename=%s%s\r\n"
                     "Content-Length: %llu\r\n"
                     "\r\n",
                     env.get_server_protocol().c_str(),
                     (isGzip ? "application/gzip" : "application/fits"),
                     filename.string().c_str(), (isGzip ? ".gz" : ""),
                     static_cast<unsigned long long>(wr.get_content_length())) < 0) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "failed to write to standard out");
    }

    // send back data
    if (std::fwrite(wr.get_content(), wr.get_content_length(), 1, stdout) != 1) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "failed to write to standard out");
    }
    return 0;
}

int serve_entire_file(const fs::path& path, const fs::path& diskpath,
                      const Environment& env, bool& sent_header) {
    validate_cutout_params(env, false);
    fs::path filename = path.filename();
    string extension = to_lower_copy(filename.extension().string());
    string contentType = "application/octet-stream";
    vector<pair<string, string> > const cts = get_content_types();
    for (vector<pair<string, string> >::const_iterator i = cts.begin(), e = cts.end();
         i != e; ++i) {
        if (i->first.find(extension) != string::npos) {
            contentType = i->second;
            break;
        }
    }
    static size_t const blocksz = 1024 * 1024;
    uintmax_t sz = fs::file_size(diskpath);
    if (sz == static_cast<uintmax_t>(-1)) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "failed to determine size of requested file");
    }
    std::shared_ptr<std::FILE> f(std::fopen(diskpath.string().c_str(), "rb"),
                                 std::fclose);
    if (!f) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "failed to open requested file");
    }
    std::shared_ptr<void> buf(std::malloc(blocksz), std::free);
    if (!buf) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "memory allocation failed");
    }

    // send back header
    sent_header = true;
    if (std::fprintf(stdout,
                     "%s 200 OK\r\n"
                     "Content-Type: %s\r\n"
                     "Content-Length: %llu\r\n"
                     "\r\n",
                     env.get_server_protocol().c_str(), contentType.c_str(),
                     static_cast<unsigned long long>(sz)) < 0) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "failed to write to standard out");
    }

    // send back data
    while (sz > 0) {
        size_t n = (sz > blocksz) ? blocksz : sz;
        if (std::fread(buf.get(), n, 1, f.get()) != 1) {
            throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                              "failed to read requested file");
        }
        if (std::fwrite(buf.get(), n, 1, stdout) != 1) {
            throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                              "failed to write to standard out");
        }
        sz -= n;
    }
    std::fflush(stdout);
    return 0;
}

int main(int argc, char const* const* argv) {
    bool sent_header = false;
    try {
        Environment env(argc, argv);
        validate(env);
        Access access(env);
        fs::path path(env.get_value_or_default("path", ""));
        fs::path prefix(env.get_value_or_default("prefix", ""));
        fs::path diskpath = fs::path(IBE_DATA_ROOT) / prefix / path;

        // -------------------------
        // Serve a directory listing
        // -------------------------
        if (fs::is_directory(diskpath)) {
            return serve_directory_listing(path, env, access, sent_header);
        } else if (!fs::is_regular_file(diskpath)) {
            // diskpath is neither a directory nor a file
            throw HTTP_EXCEPT(HttpResponseCode::NOT_FOUND);
        }

        // path refers to a regular file
        check_access(path.string(), access);  // 404 if file access isn't allowed
        fs::path filename = path.filename();
        string extension = to_lower_copy(filename.extension().string());
        if (extension == ".gz" || extension == ".fz") {
            filename = filename.stem();
            extension = to_lower_copy(filename.extension().string());
        }

        // -------------------
        // Serve a FITS cutout
        // -------------------
        if ((extension == ".fit" || extension == ".fits") &&
            env.get_num_values("center") == 1 && env.get_num_values("size") == 1) {
            return serve_fits_cutout(filename, diskpath, env, sent_header);
        }

        // --------------------
        // Serve an entire file
        // --------------------
        return serve_entire_file(path, diskpath, env, sent_header);
    } catch (HttpException const& hex) {
        if (!sent_header) {
            hex.write_error_response(std::cout);
        }
    } catch (std::exception const& ex) {
        if (!sent_header) {
            ibe::write_error_response(std::cout, ex);
        }
    } catch (...) {
        if (!sent_header) {
            ibe::write_error_response(std::cout);
        }
    }
    return 1;
}
