"""Helper functions and classes, to be used by Controllers.
"""
from contextlib import closing
from itertools import izip
import os
import re
import stat
import tempfile

import sqlalchemy as sa

from pylons import request, app_globals as g
from pylons.controllers.util import abort

import ibe.lib.formats as formats


def get_urlvars(required_vars):
    """Returns the values of each of the specified URL variables.
    """
    uv = []
    if isinstance(required_vars, basestring):
        required_vars = (required_vars,)
    for v in required_vars:
        if v not in request.urlvars:
            abort(400, v + ' not specified')
        try:
            sv = str(request.urlvars[v])
        except UnicodeEncodeError:
            # ASCII values only!
            abort(400, ' '.join([v, 'value', request.urlvars[v],
                                 'contains non-ASCII characters']))
        uv.append(sv)
    return uv

def resolve(schema_group, schema=None, table=None):
    """Returns a SchemaGroup/Schema/Table object from the given
    names.
    """
    if schema_group not in g.catalogs:
        abort(404, ' '.join(['schema_group', schema_group, 'not found']))
    obj = g.catalogs[schema_group]
    if schema is None:
        return obj
    if schema not in obj:
        abort(404, ' '.join(['schema', obj.id() + '.' + schema, 'not found']))
    obj = obj[schema]
    if table is None:
        return obj
    if table not in obj:
        abort(404, ' '.join(['table', obj.id() + '.' + table, 'not found']))
    return obj[table]

def make_ws():
    """Create a workspace directory.
    """
    d = tempfile.mkdtemp('', 'ibe_', g.workspace_root)
    os.chmod(d, stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH)
    return d

