#! /usr/bin/env python
# encoding: utf-8

def configure(conf):
    def get_param(varname,default):
        return getattr(Options.options,varname,'')or default

    conf.load('compiler_cxx wcs gsoap')

    import os
    ipac_incdir=[]
    ipac_libdir=[]
    for d in ['CM_ENV_DIR','CM_TPS_DIR']:
        env_dir=os.getenv(d)
        if not env_dir:
            break
        if d=='CM_ENV_DIR':
            env_dir=env_dir+'/core'
        if env_dir!=None:
            ipac_incdir.append(env_dir+'/include')
            ipac_libdir.append(env_dir+'/lib')

    conf.env.append_value('CPPFLAGS',['-I/usr/include/libxml2'])
    conf.env.append_value('LINKFLAGS',['-lxml2','-lz','-lm'])

    if not conf.options.ipac_dir:
        conf.options.ipac_dir=os.getenv("CM_BASE_DIR")
        if not conf.options.ipac_dir:
            conf.fatal("No value given for ipac-dir.  Tried environment "
                       + "variable $CM_BASE_DIR")

    # Find ipac
    if conf.options.ipac_dir:
        if not conf.options.ipac_incdir:
            conf.options.ipac_incdir=conf.options.ipac_dir + "/include"
        if not conf.options.ipac_libdir:
            conf.options.ipac_libdir=conf.options.ipac_dir + "/lib"
        if not conf.options.ipac_bindir:
            conf.options.ipac_bindir=conf.options.ipac_dir + "/bin"

    if conf.options.ipac_incdir:
        ipac_incdir.append(conf.options.ipac_incdir)
    if conf.options.ipac_libdir:
        ipac_libdir.append(conf.options.ipac_libdir)

    if conf.options.ipac_libs:
        ipac_libs=conf.options.ipac_libs.split()
    else:
        ipac_libs=['tbl','svc','www','password','cmd','config','encode','rome','reqlog','cfitsio','crypto','hcompress','ssoclient','m']

    ipac_fragment='extern "C" {\n' + \
        '#include "tbl.h"\n' + '#include "svc.h"\n' + \
        '#include "www.h"\n' + \
        '#include "password.h"\n' + \
        '#include "cmd.h"\n' + \
        '#include "config.h"\n' + \
        '#include "encode.h"\n' + \
        '#include "rome.h"\n' + \
        '#include "hcompress.h"\n' + \
        '#include "ssoclient.h"\n' + \
        '}\n' + \
        'int main()\n' +\
        '{\n' +\
        'isis_error();\n' + \
        ' svc_check();\n' + \
        ' keyword_count();\n' + \
        ' get_password_errmsg();\n' + \
        ' isws(\' \');\n' + \
        ' config_exists(" ");\n' + \
        ' base64len(1,2);\n' + \
        ' rome_tag_init();\n' + \
        ' hdecompress_file("in","out");\n' + \
        ' sso_init("endpoint",0,0,0,0,0,0);\n' + \
        '}\n'

    import copy
    conf.check_cc(features="cxx cxxprogram",
                  msg="Checking for IPAC base",
                  fragment=ipac_fragment,
                  includes=ipac_incdir,
                  uselib_store='ipac',
                  libpath=ipac_libdir,
                  rpath=ipac_libdir,
                  lib=ipac_libs,
                  execute=False,
                  use=['wcs','gsoap'])

    conf.find_file('isisql',[conf.options.ipac_bindir])
    conf.env['IPAC_BASE_BINDIR']=conf.options.ipac_bindir;

def options(opt):
    opt.load('wcs gsoap')

    ipac=opt.add_option_group('IPAC Options')
    ipac.add_option('--ipac-dir',
                   help='Base directory where ipac is installed')
    ipac.add_option('--ipac-incdir',
                   help='Directory where ipac include files are installed')
    ipac.add_option('--ipac-libdir',
                   help='Directory where ipac library files are installed')
    ipac.add_option('--ipac-bindir',
                   help='Directory where ipac executables are installed')
    ipac.add_option('--irsa-dir',
                   help='Directory where irsa applications are located')
    ipac.add_option('--ipac-libs',
                   help='Names of the ipac libraries without prefix or suffix\n'
                   '(e.g. "ipac")')
