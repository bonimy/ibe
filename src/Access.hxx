/** @file
 * @brief  Utilities for access control.
 * @author Serge Monkewitz
 */
#pragma once

// Local headers
#include "Environment.hxx"

// Standard library
#include <set>
#include <string>

namespace ibe {
/** Access information for a request, including the access policy
 * of the table and associated data files, as well as the set of
 * groups the requester has access to.
 */
class Access {
public:
    /// Access policies.
    enum Policy {
        DENIED = 0,
        GRANTED,

        ///< Access allowed iff user belongs to row group
        ROW_ONLY,

        ///< Access allowed iff row proprietary period has expired.
        DATE_ONLY,

        ///< Access allowed iff user belongs to row group or
        ///  row proprietary period has expired.
        ROW_DATE
    };

    Access(Environment const& env);
    ~Access();

    /// Return the access policy of the table referenced by the request.
    Policy get_policy() const { return policy_; }

    /// Return the groups the requester belongs to.
    std::set<int> const get_groups() const;

    /// Return the Postgres database connection URI and table containing
    /// file-system metadata, which is valid only for the access policies
    /// requiring row-level security checks.
    std::string const get_pg_conn() const { return pg_conn_; }
    std::string const get_pg_table() const { return pg_table_; }

private:
    Policy policy_;
    int mission_;
    int group_;
    std::string session_;
    std::string pg_conn_;
    std::string pg_table_;
    mutable std::set<int> groups_;
    mutable bool groups_valid_;
};
}  // namespace ibe
