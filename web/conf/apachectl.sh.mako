#! /bin/sh

ARGV="$@"

# Group should be allowed write permission on created files/dirs
umask 2

# Setup path
PATH="${ibe.environ['CM_STK_DIR']}/bin:/usr/bin:/bin"

# Setup load library path
LD_LIBRARY_PATH="${ibe.Dir}/env/lib"

% if 'INFORMIXDIR' in ibe.environ:
LD_LIBRARY_PATH="$LD_LIBRARY_PATH:${ibe.environ['INFORMIXDIR']}/lib:${ibe.environ['INFORMIXDIR']}/lib/esql"
% endif
# Must use an ancient version (10.2.0.5) of Oracle libraries to be compatiable with cx_Oracle
ORACLE_HOME="/usr/lib/oracle/10.2.0.5/client64"
LD_LIBRARY_PATH="$LD_LIBRARY_PATH:$ORACLE_HOME/lib"

PYTHONPATH="${ibe.environ['CM_BASE_DIR']}/lib/python"

# the path to the httpd binary, including options if necessary
HTTPD="/usr/sbin/apache2"

# These environment variables are needed by mod_wsgi applications
% if 'INFORMIXDIR' in ibe.environ:
INFORMIXDIR="${ibe.environ['INFORMIXDIR']}"
INFORMIXSERVER="${ibe.environ['INFORMIXSERVER']}"
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
export ORACLE_HOME

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

