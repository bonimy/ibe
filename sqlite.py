#! /usr/bin/env python
# encoding: utf-8

def configure(conf):
    def get_param(varname,default):
        return getattr(Options.options,varname,'')or default

    # Find sqlite 
    if conf.options.sqlite_dir:
        if not conf.options.sqlite_incdir:
            conf.options.sqlite_incdir=conf.options.sqlite_dir + "/misc/include"
        if not conf.options.sqlite_libdir:
            conf.options.sqlite_libdir=conf.options.sqlite_dir + "/misc/lib"

    if conf.options.sqlite_incdir:
        sqlite_incdir=[conf.options.sqlite_incdir]
    else:
        sqlite_incdir=[]
    if conf.options.sqlite_libdir:
        sqlite_libdir=[conf.options.sqlite_libdir]
    else:
        sqlite_libdir=[]

    if conf.options.sqlite_libs:
        sqlite_libs=conf.options.sqlite_libs.split()
    else:
        sqlite_libs=['sqlite3']

    conf.check_cc(msg="Checking for Sqlite",
                  header_name='sqlite3.h',
                  includes=sqlite_incdir,
                  uselib_store='sqlite',
                  libpath=sqlite_libdir,
                  rpath=sqlite_libdir,
                  lib=sqlite_libs)

def options(opt):
    sqlite=opt.add_option_group('Sqlite Options')
    sqlite.add_option('--sqlite-dir',
                   help='Base directory where sqlite is installed')
    sqlite.add_option('--sqlite-incdir',
                   help='Directory where sqlite include files are installed')
    sqlite.add_option('--sqlite-libdir',
                   help='Directory where sqlite library files are installed')
    sqlite.add_option('--sqlite-libs',
                   help='Names of the sqlite libraries without prefix or suffix\n'
                   '(e.g. "sqlite")')
