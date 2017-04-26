/** @file
  * @brief  Access control utility implementation.
  * @author Serge Monkewitz
  */
#include "Access.h"

#include <cstdlib>
#include <limits>

#include "boost/shared_ptr.hpp"

extern "C" {
#include "ssoclient.h"
}

using std::set;
using std::string;

namespace ibe
{

namespace
{

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
string const getSession (Environment const &env)
{
  char const *cookie = getenv ("SSO_SESSION_ID_ENV");
  if (cookie == 0)
    {
      cookie = "JOSSO_SESSIONID";
    }
  return env.getCookie (cookie, "");
}

// Return the integer value of the given parameter or the given default.
int parseInteger (Environment const &env, string const &key, int def)
{
  size_t n = env.getNumValues (key);
  if (n > 1)
    {
      throw HTTP_EXCEPT (
          HttpResponseCode::BAD_REQUEST,
          format ("%s parameter specified multiple times", key.c_str ()));
    }
  else if (n == 0)
    {
      return def;
    }
  char *s = 0;
  string const value = env.getValue (key);
  long i = std::strtol (value.c_str (), &s, 10);
  if (s == 0 || s == value.c_str ())
    {
      throw HTTP_EXCEPT (
          HttpResponseCode::BAD_REQUEST,
          format ("%s parameter value is not an integer", key.c_str ()));
    }
  if (i < std::numeric_limits<int>::min ()
      || i > std::numeric_limits<int>::max ())
    {
      throw HTTP_EXCEPT (
          HttpResponseCode::BAD_REQUEST,
          format ("%s parameter value is out of range", key.c_str ()));
    }
  return static_cast<int>(i);
}

// Return the set of mission-specific groups the user belongs to.
set<int> const getUserGroups (string const &session, int mission)
{
  if (mission < 0)
    {
      throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                         "Invalid server configuration");
    }
  set<int> groups;
  if (session.empty ())
    {
      return groups;
    }
  char const *const idmEndpoint = getenv ("SSO_IDM_ENDPOINT");
  if (idmEndpoint == 0)
    {
      throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                         "IDM endpoint not defined");
    }
  // initialize ssoclient library
  sso_init (idmEndpoint, 0, 0, 0, 0, 0, 0);
  // get user session context
  boost::shared_ptr<sso_sessionContext_t> ctx (
      sso_openUsingSessionId (const_cast<char *>(session.c_str ())),
      sso_close);
  if (!ctx || ctx->status != SSO_OK)
    {
      // Failed to retrieve session context - treat user as anonymous.
      return groups;
    }
  // iterate over user groups for mission
  sso_node_t *missionNode = 0, *groupNode = 0, *tmpNode = 0;
  HASH_FIND (hhalt, ctx->rolesById, &mission, sizeof(int), missionNode);
  if (missionNode != 0)
    {
      HASH_ITER (hhalt, missionNode->subalt, groupNode, tmpNode)
      {
        groups.insert (groupNode->id);
      }
    }
  // if the user belongs to any group for the mission, then the user
  // is allowed to see all data tagged as GROUP_NONE for that mission.
  if (!groups.empty ())
    {
      groups.insert (GROUP_NONE);
    }
  // check if the user is listed as a "super-user" (allowed to access
  // anything), and if so include GROUP_ALL in the IDs returned.
  missionNode = groupNode = tmpNode = 0;
  mission = MISSION_ALL;
  HASH_FIND (hhalt, ctx->rolesById, &mission, sizeof(int), missionNode);
  if (missionNode != 0)
    {
      int group = GROUP_ALL;
      HASH_FIND (hhalt, missionNode->subalt, &group, sizeof(int), groupNode);
      if (groupNode != 0)
        {
          groups.insert (GROUP_ALL);
        }
    }
  return groups;
}

} // unnamed namespace

Access::Access (Environment const &env)
    : _policy (DENIED), _mission (parseInteger (env, "mission", MISSION_NONE)),
      _group (parseInteger (env, "group", GROUP_NONE)),
      _session (getSession (env)), _fsDb (), _groups (), _groupsValid (false)
{
  // get access related CGI parameters and sanity check them
  string const policy = env.getValue ("policy", "ACCESS_GRANTED");
  if (env.getNumValues ("policy") > 1
      || (_mission == MISSION_NONE && _group != GROUP_NONE)
      || (_mission <= 0 && _mission != MISSION_NONE))
    {
      throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                         "Invalid server configuration");
    }
  if (policy == "ACCESS_DENIED")
    {
      _policy = DENIED;
    }
  else if (policy == "ACCESS_GRANTED")
    {
      _policy = GRANTED;
    }
  else if (policy == "ACCESS_TABLE")
    {
      if (_group == GROUP_ROW)
        {
          throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                             "Invalid server configuration");
        }
      else if (_mission == MISSION_NONE)
        {
          _policy = GRANTED;
        }
      else
        {
          _groups = getUserGroups (_session, _mission);
          _groupsValid = true;
          if (_groups.count (_group) != 0 || _groups.count (GROUP_ALL) != 0)
            {
              _policy = GRANTED;
            }
          else
            {
              _policy = DENIED;
            }
        }
    }
  else if (policy == "ACCESS_DATE_ONLY")
    {
      if (_group != GROUP_ROW)
        {
          throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                             "Invalid server configuration");
        }
      _policy = DATE_ONLY;
      _fsDb = env.getValue ("fsdb");
    }
  else if (policy == "ACCESS_ROW_ONLY" || policy == "ACCESS_ROW_DATE")
    {
      if (_mission == MISSION_NONE || _group != GROUP_ROW)
        {
          throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                             "Invalid server configuration");
        }
      _groups = getUserGroups (_session, _mission);
      _groupsValid = true;
      if (_groups.count (GROUP_ALL) != 0)
        {
          _policy = GRANTED;
        }
      else if (_groups.empty ())
        {
          _policy = (policy == "ACCESS_ROW_ONLY") ? DENIED : DATE_ONLY;
        }
      else
        {
          _policy = (policy == "ACCESS_ROW_ONLY") ? ROW_ONLY : ROW_DATE;
        }
      _fsDb = env.getValue ("fsdb");
    }
  else
    {
      throw HTTP_EXCEPT (HttpResponseCode::INTERNAL_SERVER_ERROR,
                         "Invalid server configuration");
    }
}

Access::~Access () {}

set<int> const Access::getGroups () const
{
  if (!_groupsValid)
    {
      _groups = getUserGroups (_session, _mission);
      _groupsValid = true;
    }
  return _groups;
}

} // namespace ibe
