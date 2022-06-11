#include "check_access.hxx"

// Local headers
#include "HttpException.hxx"
#include "HttpResponseCode.hxx"

// External APIs
#include <pqxx/pqxx>

// Standard library
#include <sstream>

namespace ibe {

// Return a comma separated list of the requestors groups
std::string const group_string(Access const& access);

std::string strip_trailing_slash(const fs::path& path);

void check_access(const fs::path& path, Access const& access) {
    if (access.get_policy() == Access::DENIED) {
        throw HTTP_EXCEPT(HttpResponseCode::NOT_FOUND);
    } else if (access.get_policy() != Access::GRANTED ||
               !access.get_pg_conn().empty()) {
        std::ostringstream sql;
        sql << "SELECT COUNT(*) FROM " << access.get_pg_table()
            << " WHERE\n"
               "    path_name = '"
            << path << "'";
        auto policy = access.get_policy();
        if (policy != Access::GRANTED) {
            sql << " AND\n"
                   "    (\n";
            switch (policy) {
                case Access::DATE_ONLY:
                    sql << "        ipac_pub_date < CURRENT_TIMESTAMP OR\n";
                    break;
                case Access::ROW_ONLY:
                    sql << "        ipac_gid IN (" << group_string(access) << ") OR\n";
                    break;
                case Access::ROW_DATE:
                    sql << "        ipac_gid IN (" << group_string(access)
                        << ") OR\n"
                           "        ipac_pub_date < CURRENT_TIMESTAMP OR\n";
                    break;
                default:
                    throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                                      "Invalid access config");
            }
            sql << "        is_dir = true\n"
                   "    )";
        }
        pqxx::connection conn(access.get_pg_conn());
        pqxx::work transaction(conn);

        pqxx::result resultset = transaction.exec(sql.str());

        int count;
        resultset.at(0).at(0).to(count);
        if (count == 0) {
            throw HTTP_EXCEPT(HttpResponseCode::NOT_FOUND);
        }
    }
}

std::vector<std::string> const get_dir_entries(const fs::path& diskpath,
                                               const fs::path& path,
                                               Access const& access) {
    std::ostringstream sql;
    std::string dbpath = strip_trailing_slash(path);
    sql << "SELECT path_name, is_dir FROM " << access.get_pg_table() << " WHERE\n";
    if (path.empty()) {
        sql << "    parent_path_id = 0";
    } else {
        sql << "    parent_path_id = (SELECT path_id FROM " << access.get_pg_table()
            << " WHERE path_name = '" << dbpath << "')";
    }

    auto policy = access.get_policy();
    if (policy != Access::GRANTED) {
        sql << " AND\n"
               "    (\n";
        switch (policy) {
            case Access::DATE_ONLY:
                sql << "        ipac_pub_date < CURRENT_TIMESTAMP OR\n";
                break;
            case Access::ROW_ONLY:
                sql << "        ipac_gid IN (" << group_string(access) << ") OR\n";
                break;
            case Access::ROW_DATE:
                sql << "        ipac_gid IN (" << group_string(access)
                    << ") OR\n"
                       "        ipac_pub_date < CURRENT_TIMESTAMP OR\n";
                break;
            default:
                throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                                  "Invalid access config");
        }
        sql << "        is_dir = true\n"
               "    )";
    }
    pqxx::connection conn(access.get_pg_conn());
    pqxx::work transaction(conn);

    pqxx::result resultset = transaction.exec(sql.str());

    std::vector<std::string> entries;
    bool isdir;

    for (pqxx::result::const_iterator row = resultset.begin(); row != resultset.end();
         ++row) {
        std::string f = fs::path(row[0].c_str()).filename().string();
        if (!fs::exists(diskpath / f)) {
            continue;
        }
        row[1].to(isdir);
        if (isdir) {
            f += '/';
        }
        entries.push_back(f);
    }
    return entries;
}

// Return a comma separated list of the requestors groups
std::string const group_string(Access const& access) {
    std::ostringstream oss;
    std::set<int> const groups(access.get_groups());
    std::set<int>::const_iterator i = groups.begin();
    std::set<int>::const_iterator const e = groups.end();
    while (i != e) {
        oss << *i;
        ++i;
        if (i != e) {
            oss << ',';
        }
    }
    return oss.str();
}

std::string strip_trailing_slash(const fs::path& path) {
    std::string result = path.string();
    size_t last = result.size() - 1;
    if (!result.empty() && result[last] == '/') {
        return result.substr(0, last);
    }
    return result;
}
}  // namespace ibe
