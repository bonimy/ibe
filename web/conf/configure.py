#! /usr/bin/env python
# encoding: utf-8

import glob
import grp
import json
import lxml.etree as etree
import optparse
import os, os.path
import pdb
import pwd
import re
import shutil
import socket
import stat
import subprocess
import sys

from mako.template import Template
from mako.lookup import TemplateLookup


# top-level IBE path
_ibe_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))

# required environment variables
_env_vars = ['INFORMIXDIR',
             'INFORMIXSERVER',
             'ORACLE_HOME',
             'CM_STK_DIR',
             'CM_BASE_DIR',
             'CM_TPS_DIR',
             'CM_ENV_DIR',
            ]

# If terminal supports colored text, print warning messages in RED.
def _run(cmd):
    try:
        process = subprocess.Popen(args=cmd.split(), stdout=subprocess.PIPE)
        output, _ = process.communicate()
        return '' if process.poll() else output
    except:
        return ''
_reset = _run('tput sgr0')
_bold  = _run('tput bold')
_blink = _run('tput blink')
_red   = _run('tput setaf 1')

def warning(text):
    return (_red + _bold + _blink + '\nWARNING!!' + _reset + '\n\n' +
            _red + _bold + text + '\n\n' +
            _blink + 'CONSIDER YOURSELF WARNED!\n' + _reset)


class Config(object):
    """Repository for IBE configuration parameters."""
    # attributes ommited from JSON [de]serialization
    _transient = ('environ', 'Dir', 'Rewrites')

    def __init__(self):
        self.environ = dict()
        self.Dir = _ibe_root
        self.Server = socket.getfqdn()
        self.User = pwd.getpwuid(os.getuid()).pw_name
        self.Group = grp.getgrgid(os.getgid()).gr_name
        self.ErrorLog = 'logs/error_log'
        self.CombinedLog = 'logs/combined_log'
        self.WSGISocketPrefix = 'logs/wsgi'
        self.Rewrites = []
        self.sso_idm_endpoint = 'http://irsa.ipac.caltech.edu/account/services/SSOIdentityManagerSoap'
        self.workspace_root = '/work'
        for v in _env_vars:
            if v in os.environ:
                self.environ[v] = os.environ[v]

    @classmethod
    def encode(cls, cfg):
        if not isinstance(cfg, Config):
            raise TypeError()
        o = dict()
        for k in cfg.__dict__:
            if k not in cls._transient:
                o[k] = getattr(cfg, k)
        return o

    @classmethod
    def decode(cls, obj):
        cfg= Config()
        for k in obj:
            if isinstance(k, basestring) and k not in cls._transient:
                setattr(cfg, k, obj[k])
        return cfg


def bool_input(prompt, default=False):
    """Prompt for a yes/no input from the command line."""
    val = raw_input(prompt).strip().lower()
    if len(val) == 0:
        return default
    if 'yes'.startswith(val) or 'true'.startswith(val) or val == '1':
        return True
    return False

def string_input(prompt, default=''):
    """Prompt for string from the command line."""
    val = raw_input(prompt).strip()
    if len(val) == 0:
        return default
    return val 

def is_nfs(path):
    """Check if the given path is on an NFS mounted volume. The path
       should be accessed in some way prior to this call (so that
       automount populates /proc/mounts if necessary)."""
    path = os.path.realpath(path)
    with open('/proc/mounts') as f:
        mounts = f.readlines()
    for m in mounts:
        if len(m.strip()) == 0 or m[0] == '#':
            continue
        tokens = re.split(r'([ \t]+)', m)
        if len(tokens[0]) == 0:
            tokens = tokens[2::2]
        else:
            tokens = tokens[::2]
        if len(tokens) < 3:
            continue # should never happen...
        if tokens[2].strip().lower() == 'nfs':
            if path.startswith(tokens[1]):
                return True
    return False

def prompt_for_configuration():
    """Ask user how the IBE server should be configured."""
    cfg = Config()
    # Get server admin and group
    cfg.User = string_input('User name of server processes / server admin [%s]?' % cfg.User, cfg.User)
    cfg.Group = string_input('Group name of server processes [%s]?' % cfg.Group, cfg.Group)
 
    # Get server admin group
    # Get server
    cfg.Server = string_input('Server name [%s]?' % cfg.Server, cfg.Server)
    # Get port number
    while True:
        port = raw_input('Port number [8000]? ')
        if not port:
            port = '8000'
        try:
            p = int(port)
        except:
            print port + ' is not a valid integer!'
            continue
        if p < 0 or p > 49151:
            print port + ' is not in [0, 49151]'
            continue
        break
    cfg.Port = port
    # Configure # of WSGI processes
    if bool_input('Is this an ops or test server [no]? '):
        cfg.StartServers = '4'
        cfg.MinSpareServers = '1'
        cfg.MaxSpareServers = '8'
        cfg.MaxClients = '100'
        cfg.WSGIProcesses = '8'
    else:
        cfg.StartServers = '2'
        cfg.MinSpareServers = '1'
        cfg.MaxSpareServers = '2'
        cfg.MaxClients = '100'
        cfg.WSGIProcesses = '2'
        cfg.sso_idm_endpoint = 'http://irsawebdev1.ipac.caltech.edu/account/services/SSOIdentityManagerSoap'
        cfg.workspace_root = '/work/%s_%s' % (cfg.User, cfg.Port)
    # IBE might be proxied, in which case the appropriate URLs must be generated.
    cfg.proxied = bool_input('Proxied under /ibe of an operational server [no]? ')
    cfg.host = 'http://' + cfg.Server
    if cfg.Port != 80:
        cfg.host += ':' + cfg.Port
    if cfg.proxied:
        cfg.host = raw_input('Externally visible host (e.g. http://irsa.ipac.caltech.edu)? ')
    cfg.ErrorLog = string_input(
        'HTTP error log [%s] (paths are relative to the ServerRoot)? ' % cfg.ErrorLog, cfg.ErrorLog)
    cfg.CombinedLog = string_input(
        'HTTP combined log [%s] (paths are relative to the ServerRoot)? ' % cfg.CombinedLog, cfg.CombinedLog)
    cfg.WSGISocketPrefix = string_input(
        'WSGI Socket Prefix '
        '(see https://code.google.com/p/modwsgi/wiki/ConfigurationDirectives#WSGISocketPrefix, '
        'paths are relative to the ServerRoot) [%s]? ' % cfg.WSGISocketPrefix, cfg.WSGISocketPrefix)
    # Which data sets should be served?
    cfg.datasets = []
    conf_root = os.path.join(_ibe_root, 'conf', 'catalogs')
    schema_dirs = glob.glob(os.path.join(conf_root, '*', '*'))
    for d in schema_dirs:
        if not os.path.isdir(d):
            continue
        ds = os.path.normpath(os.path.relpath(d, conf_root))
        if bool_input('Serve %s dataset [no]? ' % ds):
            cfg.datasets.append(ds)
    return cfg


def _invalid_conf(conf_file, msg):
    print >>sys.stderr, '*** ERROR: %s is an invalid XML config file: %s' % (conf_file, msg)
    sys.exit(1)


def build_rewrites(cfg, access, path):
    policy = 'ACCESS_GRANTED'
    query_params = ''
    if access is not None:
        policy = access.get('policy') or policy
        if policy != 'ACCESS_GRANTED':
            mission = access.get('mission')
            group = access.get('group')
            fsdb = access.get('fsdb')
            query_params = ['policy=' + policy]
            if mission: query_params.append('mission=' + mission)
            if group: query_params.append('group=' + group)
            if fsdb: query_params.append('fsdb=' + fsdb)
            query_params = '&'.join(query_params)
    rewrites = ['# ' + path]
    if len(query_params) == 0:
        rewrites.append('RewriteCond %{QUERY_STRING} ^(.+)$')
        rewrites.append(str.format(
            'RewriteRule ^/data/{0}/(.*\.fits(\.gz)?) '
            '/cgi-bin/nph-serve?path={0}/$1&%1 [NE,PT]', path))
        if cfg.proxied:
             rewrites.append('RewriteCond %{QUERY_STRING} ^(.+)$')
             rewrites.append(str.format(
                 'RewriteRule ^/ibe/data/{0}/(.*\.fits(\.gz)?) '
                 '/cgi-bin/nph-serve?url_root=/ibe&path={0}/$1&%1 [NE,PT]', path))
    else:
        rewrites.append('RewriteCond %{QUERY_STRING} ^(.+)$')
        rewrites.append(str.format(
            'RewriteRule ^/data/{0}/(.*\.fits(\.gz)?) '
            '/cgi-bin/nph-serve?path={0}/$1&{1}&%1 [NE,PT]', path, query_params))
        rewrites.append(str.format(
            'RewriteRule ^/data/{0}/(.*) '
            '/cgi-bin/nph-serve?path={0}/$1&{1} [NE,PT]', path, query_params))
        if cfg.proxied:
            rewrites.append('RewriteCond %{QUERY_STRING} ^(.+)$')
            rewrites.append(str.format(
                'RewriteRule ^/ibe/data/{0}/(.*\.fits(\.gz)?) '
                '/cgi-bin/nph-serve?url_root=/ibe&path={0}/$1&{1}&%1 [NE,PT]', path, query_params))
            rewrites.append(str.format(
                'RewriteRule ^/ibe/data/{0}/(.*) '
                '/cgi-bin/nph-serve?url_root=/ibe&path={0}/$1&{1} [NE,PT]', path, query_params))
    return rewrites


def deploy_dataset(cfg, ds, cat_root, data_root, docs_root):
    """Deploy a single dataset.

       - Parse XML config file for the catalogs in the dataset
       - Setup web-accessible symlink to data directory for each catalog
       - Copy docs for each catalog to web directory

       Return a pair (engines, rewrites), where engines is the set of
       database engine ids for the dataset, and rewrites is list of
       Apache rewrite rules for serving the corresponding files/cutouts.
    """
    print '\nDeploying dataset %s ...' % ds
    conf_file = os.path.join(cat_root, ds, 'catalogs.xml')
    doc_files = glob.glob(os.path.join(cat_root, ds, '*.html'))
    tree = etree.ElementTree()
    tree.parse(conf_file)
    schema_group = tree.find('/schema_group')
    schema = tree.find('/schema_group/schema')
    tables = tree.findall('/schema_group/schema/table')
    if (schema_group is None or schema_group.get('id') is None or
        schema is None or schema.get('name') is None or
        len(tables) == 0):
        _invalid_conf(conf_file, 'missing or invalid <schema_group>, <schema>, and/or <table> element(s)')
    # Make sure the directories containing the config file correspond to
    # schema_group/schema names
    engines = set()
    engine = schema.get('engine')
    if engine != None:
        engines.add(engine)
    rewrites = []
    schema_group = schema_group.get('id')
    schema = schema.get('name')
    if ds != os.path.join(schema_group, schema):
        _invalid_conf(conf_file, 'describes tables not in dataset ' + ds)
    # deploy tables one by one
    for table in tables:
        engine = table.get('engine')
        if engine != None:
            engines.add(engine)
        chunk_index = table.find('chunk_index')
        products = table.find('products')
        access = table.find('access')
        table = table.get('name')
        rewrites += build_rewrites(cfg, access, '/'.join([schema_group, schema, table]))
        if table is None:
            _invalid_conf(conf_file, '<table> element has no "name" attribute')
        if chunk_index is None or chunk_index.get('path') is None:
            _invalid_conf(conf_file, '<table> element has missing/invalid <chunk_index> child')
        chunk_index = chunk_index.get('path')
        if not os.path.isfile(chunk_index):
            _invalid_conf(conf_file, 'chunk index file %s does not exist' % chunk_index)
        if products is None:
            continue # table doesn't have associated data/documentation
        products = products.get('rootpath')
        if products is None:
            _invalid_conf(conf_file, '<product> rootpath attribute is missing')
        if not os.path.isdir(products):
            _invalid_conf(conf_file, 'product (data) directory %s does not exist' % products)
        # Create data directory links
        d = os.path.abspath(os.path.join(data_root, ds))
        if not os.path.exists(d):
            print '\t- creating directory ' + d
            os.makedirs(d)
        link_name = os.path.join(d, table)
        print '\t- symlinking ' + link_name + '\n\t    to ' + products
        os.symlink(products, link_name)
        # Now copy over table documentation, if available
        html_file = os.path.join(cat_root, ds, table + '.html')
        d = os.path.join(docs_root, ds, table)
        if os.path.isfile(html_file):
            if not os.path.exists(d):
                print '\t- creating directory ' + d
                os.makedirs(d)
            print '\t- copying ' + html_file + '\n\t    to ' + os.path.join(d, 'index.html')
            shutil.copyfile(html_file, os.path.join(d, 'index.html'))
    return engines, rewrites


def write_engines(engines, conf_root):
    # Read in all known engines
    conf_file = os.path.join(conf_root, 'all_engines.xml')
    tree = etree.ElementTree()
    tree.parse(conf_file)
    all_engines = set()
    for eng in tree.findall('/engine'):
        id = eng.get('id')
        if id is None:
            _invalid_conf(conf_file, '<engine> element has no id attribute')
        if id in all_engines:
            _invalid_conf(conf_file, 'Multiple <engine> elements share the same id')
        all_engines.add(id)
        if id not in engines:
            # this engine isn't required - remove it from the tree
            tree.getroot().remove(eng)
    # Write out required engines
    conf_file = os.path.join(conf_root, '.engines.xml.next')
    tree.write(conf_file, encoding="UTF-8", xml_declaration=True, method="xml")


def main():
    parser = optparse.OptionParser(usage="""\
usage: %prog [options]

Configure the Image-Back-End server. The configuration to use can
optionally be loaded from/saved to a file. If no input configuration
file is specified via --load, the configuration is constructed by
prompting the user for server install characteristics.
""")
    parser.add_option('-s', '--save', dest='save', metavar='FILE',
                      help='save configuration to a file')
    parser.add_option('-l', '--load', dest='load', metavar='FILE',
                      help='load configuration from a file')
    parser.add_option('-S', '--save-only', dest='save_only', metavar='FILE',
                      help='save configuration to a file without reconfiguring this IBE instance')
    options, _ = parser.parse_args()

    if options.load:
        # use prexisting config
        print '\nLoading config from ' + options.load
        with open(options.load, 'rb') as f:
            cfg = Config.decode(json.load(f))
    else:
        # new configuration based on user input
        cfg = prompt_for_configuration()

    if options.save_only:
        print '\nSaving config to ' + options.save_only + ' without reconfiguring this server'
        with open(options.save_only, 'wb') as f:
            json.dump(cfg, f, indent=4, default=Config.encode)
        return

    print '\n\nConfiguring ...'

    # make sure /ibe/(data|docs) is an alias for /(data|docs) on this server
    web_root = os.path.join(_ibe_root, 'web', 'html')
    d = os.path.join(web_root, 'ibe')
    if not os.path.exists(d):
        print '\t- creating ' + d
        os.mkdir(d)
    link_from = os.path.join(d, 'data'); to = os.path.join(os.pardir, 'data')
    print '\t- symlinking ' + link_from + '\n\t    to ' + to
    os.symlink(to, link_from + '.next')
    os.rename(link_from + '.next', link_from)
    link_from = os.path.join(d, 'docs'); to = os.path.join(os.pardir, 'docs')
    print '\t- symlinking ' + link_from + '\n\t    to ' + to
    os.symlink(to, link_from + '.next')
    os.rename(link_from + '.next', link_from)

    # Deploy requested datasets
    docs_root = os.path.join(web_root, '.docs.next')
    data_root = os.path.join(web_root, '.data.next')
    for d in docs_root, data_root:
        if os.path.exists(d):
            shutil.rmtree(d)
    cat_root = os.path.join(_ibe_root, 'conf', 'catalogs')
    engines = set()
    rewrites = []
    for ds in cfg.datasets:
        engs, rw = deploy_dataset(cfg, ds, cat_root, data_root, docs_root)
        engines.update(engs)
        rewrites += rw
    cfg.Rewrites = '\n'.join(rewrites)

    # Write out configuration files
    conf_root = os.path.join(_ibe_root, 'web', 'conf')
    module_directory = os.path.join(conf_root, '.mako')
    lookup = TemplateLookup(directories=[conf_root], module_directory=module_directory)
    apache_sh = lookup.get_template('apachectl.sh.mako')
    httpd_conf = lookup.get_template('httpd.conf.mako')
    production_ini = lookup.get_template('production.ini.mako')
    p = os.path.join(conf_root, '.apachectl.sh.next')
    print '\t- writing ' + p
    with open(p, 'w') as f:
        f.write(apache_sh.render(attributes={}, ibe=cfg))
    os.chmod(p,
             stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR |
             stat.S_IRGRP | stat.S_IXGRP |
             stat.S_IROTH | stat.S_IXOTH)
    p = os.path.join(conf_root, '.httpd.conf.next')
    print '\t- writing ' + p
    with open(p, 'w') as f:
        f.write(httpd_conf.render(attributes={}, ibe=cfg))
    p = os.path.join(_ibe_root, 'src', 'python', '.production.ini.next')
    print '\t- writing ' + p
    with open(p, 'w') as f:
        f.write(production_ini.render(attributes={}, ibe=cfg))
    print '\t- removing ' + module_directory
    shutil.rmtree(module_directory) # remove compiled templates

    # Write out XML for required database engines only
    write_engines(engines, os.path.join(_ibe_root, 'conf'))

    # Swap in new config
    print '\nSwapping in new config ...'
    # data/docs directories
    for sub in ('docs', 'data'):
        next = os.path.join(web_root, '.' + sub + '.next')
        prev = os.path.join(web_root, '.' + sub + '.prev')
        d = os.path.join(web_root, sub)
        if os.path.exists(d):
            if os.path.exists(prev):
                print '\t- removing ' + prev
                try:
                    shutil.rmtree(prev)
                except:
                    print '\t\t... failed! Please clean up manually!'
            print ('\t- moving ' + d + '\n\t    to ' + prev +
                   '\n\t  and ' + next + '\n\t    to ' + d)
            os.rename(d, prev)
        else:
            print '\t- moving ' + next + '\n\t    to ' + d
        if os.path.exists(next):
            os.rename(next, d)
    # config files
    for (d, f) in ((conf_root, 'apachectl.sh'),
                   (conf_root, 'httpd.conf'),
                   (os.path.join(_ibe_root, 'src', 'python'),'production.ini'),
                   (os.path.join(_ibe_root, 'conf'), 'engines.xml'),):
        next = os.path.join(d, '.' + f + '.next')
        prev = os.path.join(d, '.' + f + '.prev')
        f = os.path.join(d, f)
        if os.path.exists(f):
            print '\t- moving ' + f + '\n\t    to ' + prev
            os.rename(f, prev)
        print '\t- moving ' + next + '\n\t    to ' + f
        os.rename(next, f)
    # Save configuration if requested
    if options.save:
        print '\nSaving config to ' + options.save
        with open(options.save, 'wb') as f:
            json.dump(cfg, f, indent=4, default=Config.encode)

    # Sanity checks on the WSGI socket directory
    p = cfg.WSGISocketPrefix
    if not os.path.isabs(p):
        p = os.path.join(_ibe_root, 'web', p)
    p = os.path.dirname(p)
    if not os.path.exists(p):
        os.mkdir(p)
    if is_nfs(p):
        print warning('Directory for WSGI UNIX domain sockets (%s) appears to be on an NFS volume. '
                      'In the past, such configurations have led to much woe and gnashing of teeth. '
                      'This directory can be changed via the WSGISocketPrefix option.' % p)

 
if __name__ == '__main__':
    main()

