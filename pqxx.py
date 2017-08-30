#! /usr/bin/env python
# encoding: utf-8

def configure(conf):
    def get_param(varname,default):
        return getattr(Options.options,varname,'')or default

    conf.load('compiler_cxx')

    # Find PQXX
    if conf.options.pqxx_dir:
        if not conf.options.pqxx_incdir:
            conf.options.pqxx_incdir=conf.options.pqxx_dir + "/include"
        if not conf.options.pqxx_libdir:
            conf.options.pqxx_libdir=conf.options.pqxx_dir + "/lib"

    if conf.options.pqxx_incdir:
        pqxx_incdir=[conf.options.pqxx_incdir]
    else:
        pqxx_incdir=[]
    if conf.options.pqxx_libdir:
        pqxx_libdir=[conf.options.pqxx_libdir]
    else:
        pqxx_libdir=[]

    if conf.options.pqxx_libs:
        pqxx_libs=conf.options.pqxx_libs.split()
    else:
        pqxx_libs=['pqxx', 'pq']

    conf.check_cxx(msg="Checking for pqxx",
                   header_name='pqxx/pqxx',
                   includes=pqxx_incdir,
                   uselib_store='pqxx',
                   libpath=pqxx_libdir,
                   rpath=pqxx_libdir,
                   lib=pqxx_libs)

def options(opt):
    opt.load('compiler_cxx')

    pqxx=opt.add_option_group('Pqxx Options')
    pqxx.add_option('--pqxx-dir',
                   help='Base directory where pqxx is installed')
    pqxx.add_option('--pqxx-incdir',
                   help='Directory where pqxx include files are installed')
    pqxx.add_option('--pqxx-libdir',
                   help='Directory where pqxx library files are installed')
    pqxx.add_option('--pqxx-libs',
                   help='Names of the pqxx libraries without prefix or suffix\n'
                   '(e.g. "pqxx_query")')
