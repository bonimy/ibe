import os, os.path, site, sys
from paste.script.util.logging_config import fileConfig
BASEDIR = os.path.abspath(os.path.dirname(__file__))
INIFILE = os.path.join(BASEDIR, 'production.ini')

sys.path.append(BASEDIR)
os.environ['PYTHON_EGG_CACHE'] = '/tmp'

fileConfig(INIFILE)

from paste.deploy import loadapp

application = loadapp('config:%s' % INIFILE)

