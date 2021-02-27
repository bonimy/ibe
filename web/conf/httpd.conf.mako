
ServerRoot "${ibe.Dir}/web"

TraceEnable off
FileETag none
PidFile logs/httpd.pid
Timeout 400
KeepAlive On
MaxKeepAliveRequests 100
KeepAliveTimeout 15

## Server-Pool Size Regulation (MPM specific)

# prefork MPM
# StartServers: number of server processes to start
# MinSpareServers: minimum number of server processes which are kept spare
# MaxSpareServers: maximum number of server processes which are kept spare
# MaxClients: maximum number of server processes allowed to start
# MaxRequestsPerChild: maximum number of requests a server process serves
<IfModule prefork.c>
StartServers         ${ibe.StartServers}
MinSpareServers      ${ibe.MinSpareServers}
MaxSpareServers      ${ibe.MaxSpareServers}
MaxClients           ${ibe.MaxClients}
MaxRequestsPerChild  20
</IfModule>

Listen ${ibe.Port}

User ${ibe.User}
Group ${ibe.Group}
ServerAdmin ${ibe.User}@ipac.caltech.edu
ServerName ${ibe.Server}:${ibe.Port}
DocumentRoot "${ibe.Dir}/web/html"

DirectoryIndex index.html
AccessFileName .htaccess

# Prevent .htaccess and .htpasswd files from being viewed by Web clients. 
<Files ~ "^\.ht">
    Order allow,deny
    Deny from all
</Files>

# Location of the mime.types file (or equivalent) 
TypesConfig ${ibe.environ['CM_ENV_DIR']}/apache2/conf/mime.types
DefaultType text/plain
<IfModule mod_mime_magic.c>
    MIMEMagicFile ${ibe.environ['CM_ENV_DIR']}/apache2/conf/magic
</IfModule>

HostnameLookups Off

LogFormat "%h %l %u %t \"%r\" %>s %b %T \"%{Referer}i\" \"%{User-Agent}i\" id=%{UNIQUE_ID}e #%P" combined

ServerTokens Minimal
ServerSignature Off

ReadmeName README.html
HeaderName HEADER.html

# IndexIgnore is a set of filenames which directory indexing should ignore
IndexIgnore .??* *~ *# HEADER* RCS CVS *,v *,t

AddLanguage en .en
LanguagePriority en
ForceLanguagePriority Prefer Fallback
AddDefaultCharset UTF-8

AddCharset ISO-8859-1  .iso8859-1  .latin1
AddCharset UTF-8       .utf8
AddCharset utf-8       .utf8

AddType application/x-compress .Z
AddType application/x-gzip .gz .tgz
AddType image/x-fits .fits .fit

# For files that include their own HTTP headers:
AddHandler send-as-is asis

AddType text/html .html .htm 
AddOutputFilter INCLUDES .html .htm

# The following directives modify normal HTTP response behavior to
# handle known problems with browser implementations.
BrowserMatch "Mozilla/2" nokeepalive
BrowserMatch "MSIE 4\.0b2;" nokeepalive downgrade-1.0 force-response-1.0
BrowserMatch "RealPlayer 4\.0" force-response-1.0
BrowserMatch "Java/1\.0" force-response-1.0
BrowserMatch "JDK/1\.0" force-response-1.0

# The following directive disables redirects on non-GET requests for
# a directory that does not include the trailing slash.  This fixes a 
# problem with Microsoft WebFolders which does not appropriately handle 
# redirects for folders with DAV methods.
# Same deal with Apple's DAV filesystem and Gnome VFS support for DAV.
BrowserMatch "Microsoft Data Access Internet Publishing Provider" redirect-carefully
BrowserMatch "^WebDrive" redirect-carefully
BrowserMatch "^WebDAVFS/1.[012]" redirect-carefully
BrowserMatch "^gnome-vfs" redirect-carefully

ErrorLog  ${ibe.ErrorLog}
LogLevel  error
CustomLog ${ibe.CombinedLog} combined

SetEnv HOME           /tmp
SetEnv USER           ${ibe.User}
% if 'INFORMIXDIR' in ibe.environ:
SetEnv INFORMIXDIR    ${ibe.environ['INFORMIXDIR']}
SetEnv INFORMIXSERVER ${ibe.environ['INFORMIXSERVER']}
% endif
% if 'ORACLE_HOME' in ibe.environ:
SetEnv ORACLE_HOME    ${ibe.environ['ORACLE_HOME']}
% endif
SetEnv SSO_SESSION_ID_ENV JOSSO_SESSIONID
SetEnv SSO_IDM_ENDPOINT ${ibe.sso_idm_endpoint}

PassEnv PATH
PassEnv LD_LIBRARY_PATH
PassEnv PYTHONPATH

ScriptAlias /cgi-bin ${ibe.Dir}/web/cgi-bin

#WSGI setup
LoadModule wsgi_module ${ibe.environ['CM_ENV_DIR']}/apache2/modules/mod_wsgi.so

WSGIPythonHome ${ibe.Dir}/env
WSGISocketPrefix ${ibe.WSGISocketPrefix}
# The lxml module is incompatible with Python sub-interpreters,
# so don't use them to run mod_wsgi apps
WSGIApplicationGroup %{GLOBAL}
WSGIDaemonProcess ibe_${ibe.Server}:${ibe.Port} processes=${ibe.WSGIProcesses} threads=1 display-name=%{GROUP}
WSGIProcessGroup ibe_${ibe.Server}:${ibe.Port}

WSGIScriptAlias /wsgi ${ibe.Dir}/src/python/ibe.wsgi

RewriteEngine on

# Disable TRACE and TRACK
RewriteCond %{REQUEST_METHOD} ^TRACE
RewriteRule .* - [F]
RewriteCond %{REQUEST_METHOD} ^TRACK
RewriteRule .* - [F]

% if not ibe.proxied:
RewriteRule ^/ibe(.*)$ $1 [PT]
% endif

RewriteCond %{QUERY_STRING} ^(.+)$

# Allow subimage queries by simply appending query parameters to a file URL.
# Note that without the PT (pass-through) directive in RewriteRule, the
# rewritten URL is taken to be a file name and is not passed on for further
# processing (in particular, ScriptAlias will not apply, so all rewritten
# URLs will result in 404 errors).
#
# For protected data-sets, handle directory listing / file retrieval via
# a custom CGI script.
${ibe.Rewrites}

# RewriteRule ^/search/(.+) /wsgi/search/$1 [PT]
# RewriteRule ^/search/?$ /wsgi/search [PT]
# RewriteRule ^/sia/(.+) /wsgi/sia/$1 [PT]
# RewriteRule ^/sia/?$ /wsgi/sia [PT]

RewriteRule /search/(.+) /wsgi/search/$1 [PT]
RewriteRule /search/?$ /wsgi/search [PT]
RewriteRule /sia/(.+) /wsgi/sia/$1 [PT]
RewriteRule /sia/?$ /wsgi/sia [PT]

<Directory "/">
  Options All
  AllowOverride None
</Directory>

<Directory ${ibe.Dir}/src/python>
  Order allow,deny
  Allow from all
</Directory>

<Directory ${ibe.Dir}/web/html>
  Order allow,deny
  Allow from all
</Directory>

<Directory ${ibe.Dir}/web/html/data>
  Options Indexes FollowSymLinks
  AllowOverride None
</Directory>

<Directory ${ibe.Dir}/web/cgi-bin>
  AllowOverride None
  <Limit GET POST>
    Options SymLinksIfOwnerMatch
  </Limit>
</Directory>

<IfModule mod_status.c>
#
# Allow server status reports generated by mod_status,
# with the URL of http://servername/server-status
# Uncomment and change the "192.0.2.0/24" to allow access from other hosts.
#
<Location /server-status>
    SetHandler server-status
    Order deny,allow
    Deny from all
    Allow from 134.4
</Location>

# Keep track of extended status information for each request
ExtendedStatus On

# Determine if mod_status displays the first 63 characters of a request or
# the last 63, assuming the request itself is greater than 63 chars.
# Default: Off
#SeeRequestTail On

</IfModule>
