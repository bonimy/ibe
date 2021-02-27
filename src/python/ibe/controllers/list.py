from contextlib import closing, nested
from cStringIO import StringIO
from itertools import izip
import logging
import os
import traceback

from paste.httpexceptions import HTTPException
from pylons import request, response, app_globals as g
from pylons.controllers.util import abort

import sqlalchemy as sa

from ibe.lib.base import BaseController
import ibe.lib.helpers as h
import ibe.lib.utils as utils


log = logging.getLogger(__name__)

def _header(io, title):
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    io.write('''\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
\t<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
\t<title>''')
    io.write(title)
    io.write('''</title>
\t<style type="text/css">
\tbody {
\t\tfont-family: Helvetica, Arial, sans-serif;
\t\tfont-size: small;
\t\tcolor: black;
\t\tbackground-color: white;
\t}
\ttable {
\t\tborder: none;
\t\tborder-spacing: 0.5em;
\t\tmargin: 1em 1em 1em 4em;
\t}
\ttd {
\t\tmargin: 0.5em;
\t\tpadding: 0 4em 0 1em;
\t}
\ttd.category {
\t\tmargin: 0.5em;
\t\tpadding: 1em 0 0 0;
\t\tfont-weight: bold;
\t}
\t</style>
</head>
<body>
<div>
\t<h1>''')
    io.write(title)
    io.write('</h1>\n\t<table>\n')

def _footer(io):
    io.write('\t</table>\n</div>\n</body>\n</html>\n')


class ListController(BaseController):
    """Controller for listing available schema groups, schemas, tables,
    and products.
    """
    def schema_groups(self):
        """Lists available schema groups.
        """
        try:
            with closing(StringIO()) as io:
                _header(io, 'schema groups')
                for schema_group in g.catalogs:
                    io.write('\t\t<tr><td><a href="')
                    io.write('/'.join([g.url_root, 'search', schema_group]))
                    io.write('">')
                    io.write(schema_group)
                    io.write('</a></td></tr>\n')
                _footer(io)
                return io.getvalue()
        except HTTPException:
            raise
        except Exception, ex:
            abort(500, str(ex))

    def schemas(self):
        """Lists available schemas for a schema group.
        """
        try:
            schema_group, = h.get_urlvars('schema_group')
            sg = h.resolve(schema_group)
            with closing(StringIO()) as io:
                _header(io, schema_group + ' schemas')
                io.write('\t\t<tr><td><a href="')
                io.write('/'.join([g.url_root, 'search']))
                io.write('">..</a></td></tr>\n')
                for schema in sg:
                    io.write('\t\t<tr><td><a href="')
                    io.write('/'.join([g.url_root, 'search', schema_group, schema]))
                    io.write('">')
                    io.write(schema)
                    io.write('</a></td></tr>\n')
                _footer(io)
                return io.getvalue()
        except HTTPException:
            raise
        except Exception, ex:
            abort(500, str(ex))

    def tables(self):
        """Lists available tables for a schema.
        """
        try:
            schema_group, schema = h.get_urlvars(('schema_group', 'schema'))
            s = h.resolve(schema_group, schema)
            with closing(StringIO()) as io:
                _header(io, ' '.join([schema_group, schema, 'tables']))
                io.write('\t\t<tr><td><a href="')
                io.write('/'.join([g.url_root, 'search', schema_group]))
                io.write('">..</a></td><td></td><td></td></tr>\n')
                for table in s:
                    t = s[table]
                    if t.corners is None:
                        continue
                    io.write('\t\t<tr><td>')
                    io.write(table)
                    io.write('</td><td>')
                    io.write('<a href="')
                    io.write('/'.join([g.url_root, 'search', schema_group, schema, table]))
                    io.write('?FORMAT=METADATA&ct=html">columns</a>')
                    if t.products:
                        io.write(' / <a href="')
                        io.write('/'.join([g.url_root, 'data', schema_group, schema, table]))
                        io.write('">data</a> / <a href="')
                        io.write('/'.join([g.url_root, 'docs', schema_group, schema, table]))
                        io.write('/">docs</a>')
                    io.write('</td><td>')
                    if t.description:
                        io.write(t.description)
                    io.write('</td></tr>\n')
                _footer(io)
                return io.getvalue()
        except HTTPException:
            raise
        except Exception, ex:
            raise
            abort(500, str(ex))

