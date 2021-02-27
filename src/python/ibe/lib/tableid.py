from contextlib import closing
import json
import re

import sqlalchemy as sa

from pylons import request, app_globals as g
from pylons.controllers.util import abort

import ibe.lib.helpers as h


_table_re = re.compile(r'\s*([A-Za-z_]+[A-Za-z0-9_]*)\.([A-Za-z_]+[A-Za-z0-9_]*)\.([A-Za-z0-9_]*)\s*')
_args_re = re.compile(r'\((.*)\)\s*$')

def parse_table(name, trailing=False):
    """Returns a Table object from the given name, which is expected to
    be in "<schema group>.<schema>.<table>" form.
    """
    if not isinstance(name, basestring):
        abort(400, 'table name is not a string')
    m = _table_re.match(name)
    if m is None or (not trailing and m.end() != len(name)):
        abort(400, 'invalid table name: expecting ' +
              '"<schema group>.<schema>.<table>", got "' + name + '"')
    return h.resolve(*[m.group(n) for n in xrange(1,4)]), name[m.end():]

def _encode(s):
    return s.encode('ascii') if isinstance(s, unicode) else s

def parse_id_spec(id_spec, table=None):
    """Returns a Table object and a dict of column name to value mappings
    from the given id specification. This spec is expected to be of the form
    '<schema group>.<schema>.<table>("col1":value1, "col2":value2, ...)'.
    If the ``table`` argument is not None, the leading table specification
    must be omitted, and only column name/value pairs are parsed.
    """
    if table is None:
        table, id_spec = parse_table(id_spec, True)
    m = _args_re.match(id_spec)
    if m is None or len(m.groups(1)) == 0:
        abort(400, 'invalid id specification')
    # parse id column/value list
    try:
        params = json.loads('{' + m.group(1) + '}')
        # map unicode objects to ASCII strings
        params = dict((_encode(k), _encode(v)) for k,v in params.iteritems())
    except:
        abort(400, 'invalid id specification')
    # make sure column names uniquely identify a row in t
    cols = set(params.keys())
    if not any(cols == col_set for col_set in table.unique):
        abort(400, 'invalid id specification - specified columns ' +
              'do not uniquely identify a row in ' + table.id())
    return table, params


def lookup_pos(table, params):
    """Returns the position 2-tuple (ra, dec) of the specified row in ``table``.
    """
    if table.pos is None:
        abort(400, 'Table ' + t.id() + ' does not have ra,dec columns')
    sa_table = table.table()
    stmt = sa.select([c.column() for c in table.pos])
    for name in params.keys():
        stmt = stmt.where(table[name].column() == params[name])
    with closing(table.engine.connect()) as conn:
        with closing(conn.execute(stmt)) as rows:
            return rows.fetchone()


def lookup_row(table, params, columns):
    """Returns the desired columns for the specified row in ``table``.
    """
    sa_table = table.table()
    stmt = sa.select([sa_table.c[table[c].dbname] for c in columns])
    for name in params.keys():
        stmt = stmt.where(table[name].column() == params[name])
    with closing(table.engine.connect()) as conn:
        with closing(conn.execute(stmt)) as rows:
            return rows.fetchone()

