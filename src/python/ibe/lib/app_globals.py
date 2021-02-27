"""The application's Globals object"""
import glob
import os.path

import sqlalchemy

from pylons import config

from ibe.lib.catalogs import Catalogs, readCatalogs
from ibe.lib.engines import readEngines
from ibe.lib.constraints import ParserPool

class Globals(object):
    """Globals acts as a container for objects available throughout the
    life of the application
    """
    def __init__(self, conf_dir, catalog_patterns, app_conf):
        """One instance of Globals is created during application
        initialization and is available during requests via the
        'app_globals' variable.

        Reads the back-end image server configuration files in the specified
        directory. Two globals, engines and catalogs, are created, where catalogs
        is a Catalogs object containing information about the available database
        tables, and engines is a dictionary mapping database engine IDs to
        Engine objects.

        - conf_dir:         The root configuration file directory
        - catalog_patterns: A list of file name patterns (relative to conf_dir)
                            as understood by glob.glob() that specify which catalog
                            configuration files to read.        
        """
        self.workspace_root = config['ibe.workspace_root']
        if not os.path.isdir(self.workspace_root):
            raise RuntimeError(self.workspace_root + ' does not exist or is not a directory')
        if not os.path.isdir(conf_dir):
            raise RuntimeError(conf_dir + ' does not exist or is not a directory')
        # per-thread SQL parsers
        self.parser = ParserPool()
        # backend engines and catalogs
        self.engines = readEngines(os.path.join(conf_dir, 'engines.xml'),
                                   os.path.join(conf_dir, 'engines.xsd'))
        self.catalogs = Catalogs()
        catalogs_schema = os.path.join(conf_dir, 'catalogs.xsd')
        for pat in catalog_patterns:
            for path in glob.iglob(os.path.join(conf_dir, pat)):
                self.catalogs = readCatalogs(path, catalogs_schema,
                                             self.engines, self.catalogs)
        self.server = app_conf['ibe.server']
        if self.server is None or len(self.server) == 0:
            raise RuntimeError('IBE configuration file must contain an ibe.server variable!')
        self.url_root = app_conf.get('ibe.url_root', '')
        self.sso_session_id_env = app_conf.get('ibe.sso_session_id_env', 'JOSSO_SESSIONID')
