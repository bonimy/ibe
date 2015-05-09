
import os, os.path, site, sys
from paste.script.util.logging_config import fileConfig

BASEDIR = os.path.abspath(os.path.dirname(__file__))
INIFILE = os.path.join(BASEDIR, 'production.ini')

sys.path.append(BASEDIR)
os.environ['PYTHON_EGG_CACHE'] = '/tmp'


import sys, traceback

def print_exc_plus():
    """
    print usual traceback information
    followed by contents of all
    local variables in each frame
    """
    tb = sys.exc_info()[2]
    while 1:
        if not tb.tb_next:
            break
        tb = tb.tb_next
    stack = []
    f = tb.tb_frame
    while f:
        stack.append(f)
        f = f.f_back
    stack.reverse()
    traceback.print_exc()
    print "Locals by frame, innermost last"
    for frame in stack:
        print
        print "Frame %s in %s at line %s" % (frame.f_code.co_name,
                                             frame.f_code.co_filename,
                                             frame.f_lineno)
        for key, value in frame.f_locals.items():
            print "    %20s = " % key,
            # calling str() on an unknown object could fail
            try:
                print value
            except:
                print "<ERROR WHILE PRINTING VALUE>"


from paste.deploy import loadapp

fileConfig(INIFILE)

# application = loadapp('config:%s' % INIFILE)

def load_app( s ):
    try:
        return loadapp(  s )
    except:
        print_exc_plus()

application = load_app('config:%s' % INIFILE)

