#include <fcntl.h>
#include <sys/sendfile.h>
#include <sys/stat.h>
#include <sys/types.h>

#include <pqxx/pqxx>

#include <cstdio>
#include <iostream>
#include <memory>
#include <set>
#include <sstream>
#include <utility>

#include "boost/filesystem.hpp"
#include "boost/regex.hpp"

#include "Access.hxx"
#include "Cgi.hxx"
#include "Coords.hxx"

using std::make_pair;
using std::ostream;
using std::ostringstream;
using std::pair;
using std::set;
using std::string;
using std::vector;

namespace fs = boost::filesystem;

using ibe::Access;
using ibe::Coords;
using ibe::DEG;
using ibe::Environment;
using ibe::format;
using ibe::GZIPWriter;
using ibe::HttpException;
using ibe::HttpResponseCode;
using ibe::MemoryWriter;

namespace
{

// Return a vector of (filename extension, MIME content-type) pairs.
vector<pair<string, string> > const
getContentTypes ()
{
  vector<pair<string, string> > v;
  v.push_back (make_pair (".zip", "application/zip"));
  v.push_back (make_pair (".gz .tgz", "application/gzip"));
  v.push_back (make_pair ("fits", "application/fits"));
  v.push_back (make_pair (".gif", "image/gif"));
  v.push_back (make_pair (".jpg .jpeg", "image/jpeg"));
  v.push_back (make_pair (".png", "image/png"));
  v.push_back (make_pair (".htm .html", "text/html; charset=utf-8"));
  v.push_back (make_pair (".csv", "text/csv; charset=utf-8"));
  v.push_back (
      make_pair (".txt .text .tbl .md5 .anc", "text/plain; charset=utf-8"));
  return v;
}

// Perform basic sanity checking of the CGI environment, including common query
// parameters.
void
validate (ibe::Environment const &env)
{
  if (env.getServerProtocol () != "HTTP/1.1"
      && env.getServerProtocol () != "HTTP/1.0")
    {
      throw HTTP_EXCEPT (HttpResponseCode::BAD_REQUEST,
                         "Invalid protocol: use either HTTP/1.0 or HTTP/1.1");
    }
  vector<string> keys = env.getKeys ();
  set<string> allowed ({ "url_root", "policy", "mission", "group", "pgconn",
                         "pgtable", "path", "prefix", "center", "size",
                         "gzip" });
  for (vector<string>::const_iterator i = keys.begin (), e = keys.end ();
       i != e; ++i)
    {
      if (allowed.count (*i) != 1)
        {
          throw HTTP_EXCEPT (HttpResponseCode::BAD_REQUEST,
                             format ("unknown parameter: %s", i->c_str ()));
        }
    }

  // References to the parent directory are not allowed for security reasons
  fs::path path (env.getValue ("path", ""));
  string path_string = path.generic_string ();
  if (path_string.find ("..") != std::string::npos
      || (!path.empty () && path_string[0] == '/'))
    {
      throw HTTP_EXCEPT (HttpResponseCode::BAD_REQUEST);
    }
  fs::path prefix (env.getValue ("prefix", ""));
  string prefix_string = prefix.generic_string ();
  if (prefix_string.find ("..") != std::string::npos
      || (!prefix.empty ()
          && (prefix_string[0] == '/'
              || prefix_string[prefix_string.size () - 1] != '/')))
    {
      throw HTTP_EXCEPT (HttpResponseCode::BAD_REQUEST);
    }
  fs::path url_root (env.getValue ("url_root", "/"));
  string url_root_string = url_root.generic_string ();
  if (url_root.empty () || url_root_string.find ("..") != std::string::npos
      || url_root_string[0] != '/')
    {
      throw HTTP_EXCEPT (HttpResponseCode::BAD_REQUEST);
    }
}

// Check that cutout parameters are/are not present.
void
validateCutoutParams (ibe::Environment const &env, bool isCutout)
{
  size_t n = env.getNumValues ("center");
  if (isCutout && n != 1)
    {
      throw HTTP_EXCEPT (HttpResponseCode::BAD_REQUEST,
                         "center parameter must be specifed exactly once");
    }
  else if (!isCutout && n != 0)
    {
      throw HTTP_EXCEPT (HttpResponseCode::BAD_REQUEST,
                         "invalid parameter: center");
    }
  n = env.getNumValues ("size");
  if (isCutout && n != 1)
    {
      throw HTTP_EXCEPT (HttpResponseCode::BAD_REQUEST,
                         "size parameter must be specifed exactly once");
    }
  else if (!isCutout && n != 0)
    {
      throw HTTP_EXCEPT (HttpResponseCode::BAD_REQUEST,
                         "invalid parameter: size");
    }
  n = env.getNumValues ("gzip");
  if (isCutout && n > 1)
    {
      throw HTTP_EXCEPT (HttpResponseCode::BAD_REQUEST,
                         "gzip parameter must be specifed at most once");
    }
  else if (!isCutout && n != 0)
    {
      throw HTTP_EXCEPT (HttpResponseCode::BAD_REQUEST,
                         "invalid parameter: gzip");
    }
}

// Return the boolean value of the given query parameter or defaultValue.
bool
parseBool (Environment const &env, string const &key, bool defaultValue)
{
  static boost::regex const trueRe ("^\\s*(1|on?|y(es)?|t(rue)?)\\s*",
                                    boost::regex::icase);
  static boost::regex const falseRe ("^\\s*(0|no?|o(ff?)?|f(alse)?)\\s*",
                                     boost::regex::icase);

  if (!env.hasKey (key))
    {
      return defaultValue;
    }
  string const value = env.getValue (key);
  if (boost::regex_match (value, trueRe))
    {
      return true;
    }
  else if (boost::regex_match (value, falseRe))
    {
      return false;
    }
  throw HTTP_EXCEPT (
      HttpResponseCode::BAD_REQUEST,
      format ("Value of %s parameter must equal (case insensitively) one of"
              "1,y[es],t[rue],on or 0,n[o],f[alse],off",
              key.c_str ()));
  return false;
}

// Return a directory listing obtained from the file system.
vector<string> const
getDirEntries (fs::path const &path)
{
  vector<string> entries;
  for (fs::directory_iterator d = fs::directory_iterator (path),
                              e = fs::directory_iterator ();
       d != e; ++d)
    {
      if (d->status ().type () == fs::directory_file)
        {
          entries.push_back (d->path ().filename ().string () + "/");
        }
      else if (d->status ().type () == fs::regular_file)
        {
          entries.push_back (d->path ().filename ().string ());
        }
    }
  return entries;
}

// Return a comma separated list of the requestors groups
string const
groupString (Access const &access)
{
  ostringstream oss;
  set<int> const groups (access.getGroups ());
  set<int>::const_iterator i = groups.begin ();
  set<int>::const_iterator const e = groups.end ();
  while (i != e)
    {
      oss << *i;
      ++i;
      if (i != e)
        {
          oss << ',';
        }
    }
  return oss.str ();
}

string
stripTrailingSlash (fs::path const &path)
{
  string p = path.string ();
  if (!p.empty () && p[p.size () - 1] == '/')
    {
      p = p.substr (0, p.size () - 1);
    }
  return p;
}

// Return a directory listing obtained from the file system metadata database.
vector<string> const
getDirEntries (fs::path const &diskpath, fs::path const &path,
               Access const &access)
{
  ostringstream sql;
  string dbpath = stripTrailingSlash (path);
  sql << "SELECT path_name, is_dir FROM " << access.getPgTable ()
      << " WHERE\n";
  if (path.empty ())
    {
      sql << "    parent_path_id = 0";
    }
  else
    {
      sql << "    parent_path_id = (SELECT path_id FROM "
          << access.getPgTable () << " WHERE path_name = '" << dbpath << "')";
    }

  auto policy = access.getPolicy ();
  if (policy != Access::GRANTED)
    {
      sql << " AND\n"
             "    (\n";
      switch (policy)
        {
        case Access::DATE_ONLY:
          sql << "        ipac_pub_date < CURRENT_TIMESTAMP OR\n";
          break;
        case Access::ROW_ONLY:
          sql << "        ipac_gid IN (" << groupString (access) << ") OR\n";
          break;
        case Access::ROW_DATE:
          sql << "        ipac_gid IN (" << groupString (access)
              << ") OR\n"
                 "        ipac_pub_date < CURRENT_TIMESTAMP OR\n";
          break;
        default:
          throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                             "Invalid access config");
        }
      sql << "        is_dir = true\n"
             "    )";
    }
  pqxx::connection conn (access.getPgConn ());
  pqxx::work transaction (conn);

  pqxx::result resultset = transaction.exec (sql.str ());

  vector<string> entries;
  bool isdir;

  for (pqxx::result::const_iterator row = resultset.begin ();
       row != resultset.end (); ++row)
    {
      string f = fs::path (row[0].c_str ()).filename ().string ();
      if (!fs::exists (diskpath / f))
        {
          continue;
        }
      row[1].to (isdir);
      if (isdir)
        {
          f += '/';
        }
      entries.push_back (f);
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
string const
getDirListing (fs::path const &path, Environment const &env,
               Access const &access)
{
  ostringstream oss;
  vector<string> entries;
  fs::path prefix (env.getValue ("prefix", ""));
  fs::path diskpath = fs::path (IBE_DATA_ROOT) / prefix / path;
  if (access.getPolicy () == Access::GRANTED && access.getPgConn ().empty ())
    {
      entries = getDirEntries (diskpath);
    }
  else if (access.getPolicy () != Access::DENIED)
    {
      entries = getDirEntries (diskpath, path, access);
    }
  // sort directory entries by name
  std::sort (entries.begin (), entries.end ());
  // build HTML
  fs::path url_root (env.getValue ("url_root", "/"));
  fs::path url = url_root / prefix / path;
  fs::path parent = url.parent_path ();
  string a_prefix = url.filename ().string ();
  if (a_prefix == "." || path.empty ())
    {
      a_prefix.clear ();
      parent = parent.parent_path ();
    }
  else
    {
      a_prefix += "/";
    }
  oss << "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.01//EN\" "
         "\"http://www.w3.org/TR/html4/strict.dtd\">\n"
         "<html>\n"
         "<head>\n"
         "<title>Index of "
      << url.string () << "</title>\n"
      << "</head>\n"
         "<body>\n"
         "<h1>Index of "
      << url.string () << "</h1>\n"
      << "<ul>\n";
  if (!parent.empty ())
    {
      oss << "<li><a href=\"" << parent.string ()
          << "/\">Parent Directory</a></li>\n";
    }
  for (vector<string>::const_iterator i = entries.begin (), e = entries.end ();
       i != e; ++i)
    {
      oss << "<li><a href=\"" << a_prefix << *i << "\">" << *i
          << "</a></li>\n";
    }
  oss << "</ul>\n"
         "</body>\n"
         "</html>";
  return oss.str ();
}

// Check whether access to path is permitted.
// If not, respond to HTTP request with a 404 Not Found.
void
checkAccess (string const &path, Access const &access)
{
  if (access.getPolicy () == Access::DENIED)
    {
      throw HTTP_EXCEPT (HttpResponseCode::NOT_FOUND);
    }
  else if (access.getPolicy () != Access::GRANTED
           || !access.getPgConn ().empty ())
    {
      ostringstream sql;
      sql << "SELECT COUNT(*) FROM " << access.getPgTable ()
          << " WHERE\n"
             "    path_name = '"
          << path << "'";
      auto policy = access.getPolicy ();
      if (policy != Access::GRANTED)
        {
          sql << " AND\n"
                 "    (\n";
          switch (policy)
            {
            case Access::DATE_ONLY:
              sql << "        ipac_pub_date < CURRENT_TIMESTAMP OR\n";
              break;
            case Access::ROW_ONLY:
              sql << "        ipac_gid IN (" << groupString (access)
                  << ") OR\n";
              break;
            case Access::ROW_DATE:
              sql << "        ipac_gid IN (" << groupString (access)
                  << ") OR\n"
                     "        ipac_pub_date < CURRENT_TIMESTAMP OR\n";
              break;
            default:
              throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                                 "Invalid access config");
            }
          sql << "        is_dir = true\n"
                 "    )";
        }
      pqxx::connection conn (access.getPgConn ());
      pqxx::work transaction (conn);

      pqxx::result resultset = transaction.exec (sql.str ());

      int count;
      resultset.at (0).at (0).to (count);
      if (count == 0)
        {
          throw HTTP_EXCEPT (HttpResponseCode::NOT_FOUND);
        }
    }
}

} // unnamed namespace

namespace ibe
{
void stream_subimage (boost::filesystem::path const &path,
                      Coords const &center, Coords const &size,
                      Writer &writer);
Coords const parse_coords (Environment const &env, std::string const &key,
                           Units defaultUnits, bool requirePair);
}

int
main (int argc, char const *const *argv)
{
  bool sentHeader = false;
  try
    {
      Environment env (argc, argv);
      validate (env);
      Access access (env);
      fs::path path (env.getValue ("path", ""));
      fs::path prefix (env.getValue ("prefix", ""));
      fs::path diskpath = fs::path (IBE_DATA_ROOT) / prefix / path;

      // -------------------------
      // Serve a directory listing
      // -------------------------
      if (fs::is_directory (diskpath))
        {
          validateCutoutParams (env, false);
          string listing = getDirListing (path, env, access);
          sentHeader = true;
          // write HTTP header
          if (std::fprintf (::stdout,
                            "%s 200 OK\r\n"
                            "Content-Type: text/html; charset=utf-8\r\n"
                            "Content-Length: %llu\r\n"
                            "\r\n",
                            env.getServerProtocol ().c_str (),
                            static_cast<unsigned long long> (listing.size ()))
              < 0)
            {
              throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                                 "failed to write to standard out");
            }
          // send back data
          if (std::fwrite (listing.c_str (), listing.size (), 1, ::stdout)
              != 1)
            {
              throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                                 "failed to write to standard out");
            }
          return 0;
        }
      else if (!fs::is_regular_file (diskpath))
        {
          // diskpath is neither a directory nor a file
          throw HTTP_EXCEPT (HttpResponseCode::NOT_FOUND);
        }

      // path refers to a regular file
      checkAccess (path.string (), access); // 404 if file access isn't allowed
      fs::path filename = path.filename ();
      string extension = filename.extension ().string ();
      if (extension == ".gz" || extension == ".fz")
        {
          filename = filename.stem ();
          extension = filename.extension ().string ();
        }

      // -------------------
      // Serve a FITS cutout
      // -------------------
      if ((extension == ".fit" || extension == ".fits")
          && env.getNumValues ("center") == 1 && env.getNumValues ("size") == 1)
        {
          // 2. Serve a FITS cutout
          validateCutoutParams (env, true);
          bool const isGzip = parseBool (env, "gzip", true);
          Coords center = parse_coords (env, "center", DEG, true);
          Coords size = parse_coords (env, "size", DEG, false);
          // Use ChunkedWriter for HTTP 1.1? But then... no way
          // to come back with an error message when something fails in
          // the middle of a sub-image operation.
          MemoryWriter wr;
          if (isGzip)
            {
              GZIPWriter gzwr (wr);
              stream_subimage (diskpath, center, size, gzwr);
              gzwr.finish ();
            }
          else
            {
              stream_subimage (diskpath, center, size, wr);
              wr.finish ();
            }
          // send back header
          sentHeader = true;
          if (std::fprintf (
                  ::stdout,
                  "%s 200 OK\r\n"
                  "Content-Type: %s\r\n"
                  "Content-Disposition: attachment; filename=%s%s\r\n"
                  "Content-Length: %llu\r\n"
                  "\r\n",
                  env.getServerProtocol ().c_str (),
                  (isGzip ? "application/gzip" : "application/fits"),
                  filename.string ().c_str (), (isGzip ? ".gz" : ""),
                  static_cast<unsigned long long> (wr.getContentLength ()))
              < 0)
            {
              throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                                 "failed to write to standard out");
            }
          // send back data
          if (std::fwrite (wr.getContent (), wr.getContentLength (), 1,
                           ::stdout)
              != 1)
            {
              throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                                 "failed to write to standard out");
            }
          return 0;
        }

      // --------------------
      // Serve an entire file
      // --------------------
      validateCutoutParams (env, false);
      filename = path.filename ();
      extension = filename.extension ().string ();
      string contentType = "application/octet-stream";
      vector<pair<string, string> > const cts = getContentTypes ();
      for (vector<pair<string, string> >::const_iterator i = cts.begin (),
                                                         e = cts.end ();
           i != e; ++i)
        {
          if (i->first.find (extension) != string::npos)
            {
              contentType = i->second;
              break;
            }
        }
      static size_t const blocksz = 1024 * 1024;
      uintmax_t sz = fs::file_size (diskpath);
      if (sz == static_cast<uintmax_t> (-1))
        {
          throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                             "failed to determine size of requested file");
        }
      std::shared_ptr<std::FILE> f (
          std::fopen (diskpath.string ().c_str (), "rb"), std::fclose);
      if (!f)
        {
          throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                             "failed to open requested file");
        }
      std::shared_ptr<void> buf (std::malloc (blocksz), std::free);
      if (!buf)
        {
          throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                             "memory allocation failed");
        }
      // send back header
      sentHeader = true;
      if (std::fprintf (::stdout,
                        "%s 200 OK\r\n"
                        "Content-Type: %s\r\n"
                        "Content-Length: %llu\r\n"
                        "\r\n",
                        env.getServerProtocol ().c_str (),
                        contentType.c_str (),
                        static_cast<unsigned long long> (sz))
          < 0)
        {
          throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                             "failed to write to standard out");
        }
      // send back data
      while (sz > 0)
        {
          size_t n = (sz > blocksz) ? blocksz : sz;
          if (std::fread (buf.get (), n, 1, f.get ()) != 1)
            {
              throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                                 "failed to read requested file");
            }
          if (std::fwrite (buf.get (), n, 1, ::stdout) != 1)
            {
              throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                                 "failed to write to standard out");
            }
          sz -= n;
        }
      std::fflush (::stdout);
      return 0;
    }
  catch (HttpException const &hex)
    {
      if (!sentHeader)
        {
          hex.writeErrorResponse (std::cout);
        }
    }
  catch (std::exception const &ex)
    {
      if (!sentHeader)
        {
          ibe::writeErrorResponse (std::cout, ex);
        }
    }
  catch (...)
    {
      if (!sentHeader)
        {
          ibe::writeErrorResponse (std::cout);
        }
    }
  return 1;
}
