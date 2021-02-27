#! /bin/sh

ARGV="$@"

# Group should be allowed write permission on created files/dirs
umask 2

# Setup path
PATH="${ibe.environ['CM_STK_DIR']}/bin:${ibe.environ['CM_TPS_DIR']}/bin:${ibe.environ['CM_ENV_DIR']}/apache2/bin:${ibe.environ['CM_ENV_DIR']}/core/bin:/usr/bin:/bin"

# Setup load library path
LD_LIBRARY_PATH="${ibe.Dir}/env/lib"

% if 'INFORMIXDIR' in ibe.environ:
LD_LIBRARY_PATH="$LD_LIBRARY_PATH:${ibe.environ['INFORMIXDIR']}/lib:${ibe.environ['INFORMIXDIR']}/lib/esql"
% endif
% if 'ORACLE_HOME' in ibe.environ:
LD_LIBRARY_PATH="$LD_LIBRARY_PATH:${ibe.environ['ORACLE_HOME']}/lib"
%endif
LD_LIBRARY_PATH="$LD_LIBRARY_PATH:${ibe.environ['CM_ENV_DIR']}/apache2/lib:${ibe.environ['CM_ENV_DIR']}/core/lib64:${ibe.environ['CM_ENV_DIR']}/core/lib"

PYTHONPATH="${ibe.environ['CM_BASE_DIR']}/lib/python"

# the path to the httpd binary, including options if necessary
HTTPD="${ibe.environ['CM_ENV_DIR']}/apache2/bin/httpd"

# These environment variables are needed by mod_wsgi applications
% if 'INFORMIXDIR' in ibe.environ:
INFORMIXDIR="${ibe.environ['INFORMIXDIR']}"
INFORMIXSERVER="${ibe.environ['INFORMIXSERVER']}"
% endif
% if 'ORACLE_HOME' in ibe.environ:
ORACLE_HOME="${ibe.environ['ORACLE_HOME']}"
% endif

# Set this variable to a command that increases the maximum
# number of file descriptors allowed per child process. This is
# critical for configurations that use many file descriptors,
# such as mass vhosting, or a multithreaded server.
ULIMIT_MAX_FILES="ulimit -S -n `ulimit -H -n`"

export PATH LD_LIBRARY_PATH PYTHONPATH
% if 'INFORMIXDIR' in ibe.environ:
export INFORMIXDIR INFORMIXSERVER
% endif
% if 'ORACLE_HOME' in ibe.environ:
export ORACLE_HOME
%endif

# Set the maximum number of file descriptors allowed per child process.
if [ "x$ULIMIT_MAX_FILES" != "x" ] ; then
    $ULIMIT_MAX_FILES
fi

ERROR=0
if [ "x$ARGV" = "x" ] ; then 
    ARGV="-h"
fi

case $ARGV in
start|stop|restart|graceful)
    $HTTPD -k $ARGV -f "${ibe.Dir}/web/conf/httpd.conf"
    ERROR=$?
    ;;
configtest)
    $HTTPD -t "${ibe.Dir}/web/conf/httpd.conf"
    ERROR=$?
    ;;
*)
    echo "Error: invalid apachectl option"
    ERROR=1
esac

exit $ERROR

