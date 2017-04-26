/** @file
  * @brief  Utility classes for SQLite.
  * @author Serge Monkewitz
  */
#ifndef SQLITE_H_
#define SQLITE_H_

#include <stdint.h>
#include <string>
#include <utility>

#include "sqlite3.h"

namespace ibe
{

class SqliteStmt;

/** RAII class that wraps a SQLite database.
  */
class SqliteDb
{
public:
  SqliteDb (std::string const &filename);
  ~SqliteDb ();

private:
  sqlite3 *_db;
  friend class SqliteStmt;
};

/** Convenience wrapper for a SQLite prepared statement.
  */
class SqliteStmt
{
public:
  SqliteStmt (SqliteDb &db, std::string const &stmt);
  ~SqliteStmt ();

  // Bind a value to the prepared statement - call before exec().
  void bind (int i);                       ///< Bind a NULL.
  void bind (int i, int val);              ///< Bind an int.
  void bind (int i, int64_t val);          ///< Bind a 64-bit int.
  void bind (int i, double val);           ///< Bind a double.
  void bind (int i, std::string const &s); ///< Bind a string.

  /// Execute the prepared statement.
  void exec ();

  /// Return true if there are results - call step() to advance through them.
  bool haveRow () const { return _status == SQLITE_ROW; }

  /// Advance to the next result row.
  void step ();

  // Retrieve a (value, isNull) pair from the current row -
  // call after exec()/step() if haveRow().
  std::pair<int, bool> const getInt (int i);
  std::pair<int64_t, bool> const getInt64 (int i);
  std::pair<double, bool> const getDouble (int i);
  std::pair<std::string, bool> const getString (int i);

private:
  sqlite3_stmt *_stmt;
  int _status;
};

} // namespace ibe

#endif // SQLITE_H_
