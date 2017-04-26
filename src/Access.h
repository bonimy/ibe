/** @file
  * @brief  Utilities for access control.
  * @author Serge Monkewitz
  */
#ifndef ACCESS_H_
#define ACCESS_H_

#include <string>
#include <set>

#include "Cgi.h"

namespace ibe
{

/** Access information for a request, including the access policy
  * of the table and associated data files, as well as the set of
  * groups the requestor has access to.
  */
class Access
{
public:
  /// Access policies.
  enum Policy
  {
    DENIED = 0,
    GRANTED,
    ROW_ONLY,  ///< Access allowed iff user belongs to row group
    DATE_ONLY, ///< Access allowed iff row proprietary period has expired.
    ROW_DATE   ///< Access allowed iff user belongs to row group or
               ///  row proprietary period has expired.
  };

  Access (Environment const &env);
  ~Access ();

  /// Return the access policy of the table referenced by the request.
  Policy getPolicy () const { return _policy; }

  /// Return the groups the requestor belongs to.
  std::set<int> const getGroups () const;

  /// Return the SQLite3 database file containing file-system metadata,
  /// which is valid only for the access policies requiring row-level
  /// security checks.
  std::string const getFsDb () const { return _fsDb; }

private:
  Policy _policy;
  int _mission;
  int _group;
  std::string _session;
  std::string _fsDb;
  mutable std::set<int> _groups;
  mutable bool _groupsValid;
};

} // namespace ibe

#endif // ACCESS_H_
