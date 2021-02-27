"""Pylons environment configuration"""
import os

from pylons import config

import ibe.lib.app_globals as app_globals
import ibe.lib.helpers
from ibe.config.routing import make_map

# Read in the ssoclient library.
from ipac.ssoclient import sso_init

def load_environment(global_conf, app_conf):
    """Configure the Pylons environment via the ``pylons.config``
    object
    """
    # Pylons paths
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths = dict(root=root,
                 controllers=os.path.join(root, 'controllers'),
                 static_files=os.path.join(root, 'public'),
                 templates=[os.path.join(root, 'templates')])

    # Initialize config with the basic options
    config.init_app(global_conf, app_conf, package='ibe', paths=paths)

    # Create route mapper and application globals
    mapper = make_map()
    ag = app_globals.Globals(app_conf['ibe.conf_dir'], app_conf['ibe.conf_files'].split(' '), app_conf)
    # Connect routes
    ag.catalogs.connectRoutes(mapper)
    config['routes.map'] = mapper
    config['pylons.app_globals'] = ag
    config['pylons.h'] = ibe.lib.helpers
    # SSO client setup
    sso_init(app_conf['ibe.sso_idm_endpoint'], None, None, None, app_conf['ibe.sso_session_id_env'], None, None)
