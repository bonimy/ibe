# ibe - Pylons environment configuration
#
# The %(here)s variable will be replaced with the parent directory of this file
<%
    import os.path
    datasets = " ".join(os.path.join("catalogs", ds, "catalogs.xml") for ds in ibe.datasets)
%>
[DEFAULT]
debug = true
email_to = ${ibe.User}@ipac.caltech.edu
smtp_server = mail0.ipac.caltech.edu
error_email_from = ${ibe.User}@ipac.caltech.edu

[server:main]
use = egg:Paste#http
host = ${ibe.Server}
port = ${ibe.Port}

[app:main]
use = egg:ibe
full_stack = true
static_files = false
ibe.conf_dir = %(here)s/../../conf
ibe.conf_files = ${datasets}
% if ibe.proxied:
ibe.url_root = /ibe
% endif
ibe.sso_session_id_env = JOSSO_SESSIONID
ibe.sso_idm_endpoint = ${ibe.sso_idm_endpoint}
ibe.workspace_root = ${ibe.workspace_root}
ibe.server = ${ibe.host}

# WARNING: *THE LINE BELOW MUST BE UNCOMMENTED ON A PRODUCTION ENVIRONMENT*
# Debug mode will enable the interactive debugging tool, allowing ANYONE to
# execute malicious code after an exception is raised.
set debug = false

# Logging configuration
[loggers]
keys = root, routes, ibe, sqlalchemy

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = INFO
handlers = console

[logger_routes]
level = INFO
handlers =
qualname = routes.middleware
# "level = DEBUG" logs the route matched and routing variables.

[logger_ibe]
level = DEBUG
handlers =
qualname = ibe

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine
# "level = INFO" logs SQL queries.
# "level = DEBUG" logs SQL queries and results.
# "level = WARN" logs neither.  (Recommended for production systems.)

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(asctime)s,%(msecs)03d %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S

