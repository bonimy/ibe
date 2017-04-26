/** @file
  * @brief  SQLite wrapper implementation.
  * @author Serge Monkewitz
  */
#include "Sqlite.h"

#include "Cgi.h"

using std::make_pair;
using std::pair;
using std::string;

namespace ibe
{

// == SqliteDb implementation ----

SqliteDb::SqliteDb (string const &filename) : _db (NULL)
{
  int flags = SQLITE_OPEN_READONLY | SQLITE_OPEN_PRIVATECACHE
              | SQLITE_OPEN_NOMUTEX;
  if (SQLITE_OK != sqlite3_open_v2 (filename.c_str (), &_db, flags, NULL))
    {
      if (_db != NULL)
        {
          sqlite3_close (_db);
        }
      throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                         "Failed to open SQLite database.");
    }
}

SqliteDb::~SqliteDb ()
{
  if (_db != NULL)
    {
      sqlite3_close (_db);
    }
}

// == SqliteStmt implementation ----

SqliteStmt::SqliteStmt (SqliteDb &db, string const &stmt)
    : _stmt (0), _status (SQLITE_OK)
{
  _status = sqlite3_prepare_v2 (db._db, stmt.c_str (),
                                static_cast<int>(stmt.size ()), &_stmt, NULL);
  if (_status != SQLITE_OK)
    {
      throw HTTP_EXCEPT (
          HttpResponseCode::INTERNAL_SERVER_ERROR,
          format ("Failed to prepare statement: %s", stmt.c_str ()));
    }
}

SqliteStmt::~SqliteStmt ()
{
  if (_stmt != 0)
    {
      sqlite3_finalize (_stmt);
    }
}

void SqliteStmt::bind (int i)
{
  if (sqlite3_bind_null (_stmt, i) != SQLITE_OK)
    {
      throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                         "Failed to bind null to sqlite prepared statement.");
    }
}

void SqliteStmt::bind (int i, int val)
{
  if (sqlite3_bind_int (_stmt, i, val) != SQLITE_OK)
    {
      throw HTTP_EXCEPT (
          HttpResponseCode::INTERNAL_SERVER_ERROR,
          "Failed to bind integer to sqlite prepared statement.");
    }
}

void SqliteStmt::bind (int i, int64_t val)
{
  if (sqlite3_bind_int64 (_stmt, i, val) != SQLITE_OK)
    {
      throw HTTP_EXCEPT (
          HttpResponseCode::INTERNAL_SERVER_ERROR,
          "Failed to bind integer to sqlite prepared statement.");
    }
}

void SqliteStmt::bind (int i, double val)
{
  if (sqlite3_bind_double (_stmt, i, val) != SQLITE_OK)
    {
      throw HTTP_EXCEPT (
          HttpResponseCode::INTERNAL_SERVER_ERROR,
          "Failed to bind double to sqlite prepared statement.");
    }
}

void SqliteStmt::bind (int i, string const &s)
{
  if (sqlite3_bind_text (_stmt, i, s.c_str (), static_cast<int>(s.size ()),
                         SQLITE_TRANSIENT) != SQLITE_OK)
    {
      throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                         "Failed to bind text to sqlite prepared statement.");
    }
}

void SqliteStmt::exec ()
{
  _status = sqlite3_reset (_stmt);
  if (_status != SQLITE_OK)
    {
      throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                         "Failed to reset prepared statement.");
    }
  _status = sqlite3_step (_stmt);
  if (_status != SQLITE_DONE && _status != SQLITE_ROW)
    {
      throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                         "Failed to execute statement.");
    }
}

// This is a macro rather than a helper function so that exceptions
// contain useful line number information.
#define REQUIRE_ROW                                                           \
  if (!haveRow ())                                                            \
    {                                                                         \
      throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,             \
                         "Query execution failed, or the result set "         \
                         "has already been exhausted.");                      \
    }

void SqliteStmt::step ()
{
  REQUIRE_ROW
  _status = sqlite3_step (_stmt);
  if (_status != SQLITE_DONE && _status != SQLITE_ROW)
    {
      throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                         "Failed to step through SQL query results.");
    }
}

pair<int, bool> const SqliteStmt::getInt (int i)
{
  REQUIRE_ROW
  // sqlite3_column_type() call must come first
  bool isNull = sqlite3_column_type (_stmt, i) == SQLITE_NULL;
  int val = sqlite3_column_int (_stmt, i);
  return make_pair (val, isNull);
}

pair<int64_t, bool> const SqliteStmt::getInt64 (int i)
{
  REQUIRE_ROW
  // sqlite3_column_type() call must come first
  bool isNull = sqlite3_column_type (_stmt, i) == SQLITE_NULL;
  int64_t val = sqlite3_column_int64 (_stmt, i);
  return make_pair (val, isNull);
}

pair<double, bool> const SqliteStmt::getDouble (int i)
{
  REQUIRE_ROW
  // sqlite3_column_type() call must come first
  bool isNull = sqlite3_column_type (_stmt, i) == SQLITE_NULL;
  double val = sqlite3_column_double (_stmt, i);
  return make_pair (val, isNull);
}

pair<string, bool> const SqliteStmt::getString (int i)
{
  REQUIRE_ROW
  // sqlite3_column_type() call must come first
  bool isNull = sqlite3_column_type (_stmt, i) == SQLITE_NULL;
  // Note: this won't work for strings with embedded NULs.
  char const *val
      = reinterpret_cast<char const *>(sqlite3_column_text (_stmt, i));
  string s = (val == 0 ? string () : string (val));
  return make_pair (s, isNull);
}

#undef REQUIRE_ROW

} // namespace ibe
