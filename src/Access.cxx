/** @file
 * @brief  Access control utility implementation.
 * @author Serge Monkewitz
 */
#include "Access.hxx"

// Local headers
#include "HttpException.hxx"
#include "HttpResponseCode.hxx"
#include "format.hxx"

// External APIs
extern "C" {
#include "ssoclient.h"
}

// Standard library
#include <cstdlib>
#include <limits>
#include <memory>

using std::set;
using std::string;

namespace ibe {
namespace {

// Special user group granting access to all user groups
int const GROUP_ALL = -99;

// Special table group for public tables
int const GROUP_NONE = -1;

// Special table group indicating access checks must
// happen at the level of individual table rows.
int const GROUP_ROW = 0;

// Special mission ID (used by Gator), semantics unclear.
int const MISSION_NONE = -1;

// Special mission ID (used by Gator), semantics unclear.
int const MISSION_ALL = -99;

// Return the user session ID or an empty string.
string const get_session(Environment const& env) {
    char const* cookie = getenv("SSO_SESSION_ID_ENV");
    if (cookie == 0) {
        cookie = "JOSSO_SESSIONID";
    }
    return env.get_cookie(cookie, "");
}

// Return the integer value of the given parameter or the given default.
int parse_integer(Environment const& env, string const& key, int def) {
    size_t n = env.get_num_values(key);
    if (n > 1) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                          format("%s parameter specified multiple times", key.c_str()));
    } else if (n == 0) {
        return def;
    }
    char* s = 0;
    string const value = env.get_value(key);
    long i = std::strtol(value.c_str(), &s, 10);
    if (s == 0 || s == value.c_str()) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                          format("%s parameter value is not an integer", key.c_str()));
    }
    if (i < std::numeric_limits<int>::min() || i > std::numeric_limits<int>::max()) {
        throw HTTP_EXCEPT(HttpResponseCode::BAD_REQUEST,
                          format("%s parameter value is out of range", key.c_str()));
    }
    return static_cast<int>(i);
}

// Return the set of mission-specific groups the user belongs to.
set<int> const get_user_groups(string const& session, int mission) {
    if (mission < 0) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "Invalid server configuration");
    }
    set<int> groups;
    if (session.empty()) {
        return groups;
    }
    char const* const idmEndpoint = getenv("SSO_IDM_ENDPOINT");
    if (idmEndpoint == 0) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "IDM endpoint not defined");
    }

    // initialize ssoclient library
    sso_init(idmEndpoint, 0, 0, 0, 0, 0, 0);

    // get user session context
    std::shared_ptr<sso_sessionContext_t> ctx(
            sso_openUsingSessionId(const_cast<char*>(session.c_str())), sso_close);
    if (!ctx || ctx->status != SSO_OK) {
        // Failed to retrieve session context - treat user as anonymous.
        return groups;
    }

    // iterate over user groups for mission
    sso_node_t *missionNode = 0, *groupNode = 0, *tmpNode = 0;
    HASH_FIND(hhalt, ctx->rolesById, &mission, sizeof(int), missionNode);
    if (missionNode != 0) {
        HASH_ITER(hhalt, missionNode->subalt, groupNode, tmpNode) {
            groups.insert(groupNode->id);
        }
    }

    // if the user belongs to any group for the mission, then the user
    // is allowed to see all data tagged as GROUP_NONE for that mission.
    if (!groups.empty()) {
        groups.insert(GROUP_NONE);
    }

    // check if the user is listed as a "super-user" (allowed to access
    // anything), and if so include GROUP_ALL in the IDs returned.
    missionNode = groupNode = tmpNode = 0;
    mission = MISSION_ALL;
    HASH_FIND(hhalt, ctx->rolesById, &mission, sizeof(int), missionNode);
    if (missionNode != 0) {
        int group = GROUP_ALL;
        HASH_FIND(hhalt, missionNode->subalt, &group, sizeof(int), groupNode);
        if (groupNode != 0) {
            groups.insert(GROUP_ALL);
        }
    }
    return groups;
}
}  // unnamed namespace

Access::Access(Environment const& env)
        : policy_(DENIED),
          mission_(parse_integer(env, "mission", MISSION_NONE)),
          group_(parse_integer(env, "group", GROUP_NONE)),
          session_(get_session(env)),
          pg_conn_(),
          pg_table_(),
          groups_(),
          groups_valid_(false) {
    // get access related CGI parameters and sanity check them
    string const policy = env.get_value_or_default("policy", "ACCESS_GRANTED");
    if (env.get_num_values("policy") > 1 ||
        (mission_ == MISSION_NONE && group_ != GROUP_NONE) ||
        (mission_ <= 0 && mission_ != MISSION_NONE)) {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "Invalid server configuration");
    }
    if (policy == "ACCESS_DENIED") {
        policy_ = DENIED;
    } else if (policy == "ACCESS_GRANTED") {
        policy_ = GRANTED;
        pg_conn_ = env.get_value_or_default("pgconn", "");
        pg_table_ = env.get_value_or_default("pgtable", "");
    } else if (policy == "ACCESS_TABLE") {
        if (group_ == GROUP_ROW) {
            throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                              "Invalid server configuration");
        } else if (mission_ == MISSION_NONE) {
            policy_ = GRANTED;
        } else {
            groups_ = get_user_groups(session_, mission_);
            groups_valid_ = true;
            if (groups_.count(group_) != 0 || groups_.count(GROUP_ALL) != 0) {
                policy_ = GRANTED;
            } else {
                policy_ = DENIED;
            }
        }
    } else if (policy == "ACCESS_DATE_ONLY") {
        if (group_ != GROUP_ROW) {
            throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                              "Invalid server configuration");
        }
        policy_ = DATE_ONLY;
        pg_conn_ = env.get_value("pgconn");
        pg_table_ = env.get_value("pgtable");
    } else if (policy == "ACCESS_ROW_ONLY" || policy == "ACCESS_ROW_DATE") {
        if (mission_ == MISSION_NONE || group_ != GROUP_ROW) {
            throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                              "Invalid server configuration");
        }
        groups_ = get_user_groups(session_, mission_);
        groups_valid_ = true;
        if (groups_.count(GROUP_ALL) != 0) {
            policy_ = GRANTED;
        } else if (groups_.empty()) {
            policy_ = (policy == "ACCESS_ROW_ONLY") ? DENIED : DATE_ONLY;
        } else {
            policy_ = (policy == "ACCESS_ROW_ONLY") ? ROW_ONLY : ROW_DATE;
        }
        pg_conn_ = env.get_value("pgconn");
        pg_table_ = env.get_value("pgtable");
    } else {
        throw HTTP_EXCEPT(HttpResponseCode::INTERNAL_SERVER_ERROR,
                          "Invalid server configuration");
    }
}

Access::~Access() {}

set<int> const Access::get_groups() const {
    if (!groups_valid_) {
        groups_ = get_user_groups(session_, mission_);
        groups_valid_ = true;
    }
    return groups_;
}
}  // namespace ibe
