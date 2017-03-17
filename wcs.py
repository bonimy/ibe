#! /usr/bin/env python
# encoding: utf-8

def configure(conf):
    def get_param(varname,default):
        return getattr(Options.options,varname,'')or default

    conf.load('compiler_cxx')

    # Find WCS
    if conf.options.wcs_dir:
        if not conf.options.wcs_incdir:
            conf.options.wcs_incdir=conf.options.wcs_dir + "/include"
        if not conf.options.wcs_libdir:
            conf.options.wcs_libdir=conf.options.wcs_dir + "/lib"

    if conf.options.wcs_incdir:
        wcs_incdir=[conf.options.wcs_incdir]
    else:
        wcs_incdir=[]
    if conf.options.wcs_libdir:
        wcs_libdir=[conf.options.wcs_libdir]
    else:
        wcs_libdir=[]

    if conf.options.wcs_libs:
        wcs_libs=conf.options.wcs_libs.split()
    else:
        wcs_libs=[]

    if not wcs_libs:
        found_wcs=False
        for wcs_lib in ['wcs','wcstools']:
            msg="Checking for " + wcs_lib
            includes=wcs_incdir
            if wcs_lib=='wcs' and not wcs_incdir:
                includes="/usr/include/wcslib"
            if wcs_lib=='wcstools' and not wcs_incdir:
                includes="/usr/include/wcstools"
            try:
                conf.check_cxx(msg=msg,
                               header_name='wcs.h',
                               includes=includes,
                               uselib_store='wcs',
                               libpath=wcs_libdir,
                               rpath=wcs_libdir,
                               lib=wcs_lib)
            except conf.errors.ConfigurationError:
                continue
            else:
                found_wcs=True
            break
        if not found_wcs:
            conf.fatal("Could not find WCS libraries")
    else:
        msg="Checking for wcs"
        conf.check_cxx(msg=msg,
                       header_name='wcs.h',
                       includes=includes,
                       uselib_store='wcs',
                       libpath=wcs_libdir,
                       rpath=wcs_libdir,
                       lib=wcs_libs)

def options(opt):
    opt.load('compiler_cxx')

    wcs=opt.add_option_group('WCS Options')
    wcs.add_option('--wcs-dir',
                   help='Base directory where wcs is installed')
    wcs.add_option('--wcs-incdir',
                   help='Directory where wcs include files are installed')
    wcs.add_option('--wcs-libdir',
                   help='Directory where wcs library files are installed')
    wcs.add_option('--wcs-libs',
                   help='Names of the wcs libraries without prefix or suffix\n'
                   '(e.g. "wcs" or "wcstools")')
