#! /usr/bin/env python
# encoding: utf-8

def configure(conf):
    def get_param(varname,default):
        return getattr(Options.options,varname,'')or default

    import os
    if not conf.options.irsa_dir:
        conf.options.irsa_dir=os.getenv("CM_IRSA_DIR")
        if not conf.options.irsa_dir:
            conf.options.irsa_dir=os.getenv("CM_BASE_APP_DIR")
            if not conf.options.irsa_dir:
                conf.fatal("No value given for irsa-dir.  Tried environment "
                           + "variables $CM_IRSA_DIR and $CM_BASE_APP_DIR")

    conf.env['IRSA_DIR']=conf.options.irsa_dir
    conf.env['DATA_DIR']=conf.options.irsa_dir + "/share";
    conf.env['WEB_CONF_DIR']=conf.options.irsa_dir + "/web/conf";
    conf.env['APP_DIR']=conf.options.irsa_dir + "/web/applications";
    conf.env['WEB_CGI_DIR']=conf.options.irsa_dir + "/web/cgi-bin";
    conf.env['HTML_DIR']=conf.options.irsa_dir + "/web/html";
                   

def options(opt):
    irsa=opt.add_option_group('IRSA Options')
    irsa.add_option('--irsa-dir',
                    help='Directory where irsa applications are located. '
                    + 'Defaults are, in order, '
                    + '$CM_IRSA_DIR and $CM_BASE_APP_DIR')
