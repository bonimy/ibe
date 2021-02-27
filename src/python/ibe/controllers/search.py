from contextlib import closing, nested
from cStringIO import StringIO
import json
import logging
import math
import os
import re
import shutil
import traceback

import numpy
import pywcs

from paste.httpexceptions import HTTPException
from pylons import request, response, app_globals as g
from pylons.controllers.util import abort

import ipac.ssoclient as ssoc

from ibe.lib.base import BaseController
import ibe.lib.catalogs as cat
import ibe.lib.constraints as constraints
import ibe.lib.formats as formats
import ibe.lib.geom as geom
import ibe.lib.helpers as h
import ibe.lib.tableid as tableid
import ibe.lib.utils as utils
import ibe.lib.streamer as streamer

log = logging.getLogger(__name__)

# -- argument parsing/extraction ----

def _get_POS(arg):
    """Extracts the value of the SIA POS parameter. Above and beyond the
    SIA specification, one can specify unique identifiers for a table row;
    a position is then extracted from that table row.
    """
    if arg is None:
        return None
    if ' ' in arg:
        abort(400, 'POS contains embedded whitespace')
    values = arg.split(',')
    if len(values) != 2:
        abort(400, 'Invalid POS (' + arg + '): expecting RA,Dec')
    try:
        ra, dec = float(values[0]), float(values[1])
    except:
        abort(400, 'Invalid POS (' + arg +
              '): RA and/or Dec are not valid floating point numbers')
    if ra < 0.0 or ra > 360.0:
        abort(400, str.format('RA value {0!r} is out of range [0,360]', ra))
    if dec < -90.0 or dec > 90.0:
        abort(400, str.format('Dec value {0!r} is out of range [-90,90]', dec))
    return ra, dec

def _get_refby(arg, to_table):
    """Extracts the value of the refby parameter, looks up the row with the
    given id, and then constructs a query on to_table using the values of
    columns that reference to_table columns.
    """
    if arg is None:
        return None
    t, params = tableid.parse_id_spec(arg)
    refs = t.refs_to(to_table)
    if not refs:
        abort(400, 'Row identified by ' + arg + ' cannot be used to lookup ' +
              'rows in ' + to_table.id() + ' - the two tables are unrelated')
    # lookup columns in t that link row to to_table
    tcols = [r[0] for r in refs]
    row = tableid.lookup_row(t, params, tcols)
    if row is None:
        abort(400, arg + ' does not identify any row in ' + to_table.id())
    # now, build an AST for a query that retrieves rows from to_table with
    # those column values
    cvmap = dict(((r[1], row[r[0]]) for r in refs))
    return constraints.cvmap_to_ast(cvmap)

def _get_SIZE(arg):
    """Extracts the value of the SIA SIZE parameter.
    """
    if arg is None:
        return 0.0, 0.0
    if ' ' in arg:
        abort(400, 'SIZE parameter contains embedded whitespace')
    values = arg.split(',')
    if len(values) not in (1, 2):
        abort(400, 'Invalid SIZE (' + arg +
              '): expecting one or two (comma separated) axis sizes in decimal degrees')
    try:
        s1, s2 = float(values[0]), float(values[min(1, len(values) - 1)])
    except:
        abort(400, 'Invalid SIZE (' + arg +
              '): SIZE contains an invalid floating point number')
    if s1 < 0.0 or s2 < 0.0:
        abort(400, 'Invalid SIZE (' + arg + '): negative size')
    if s1 == 0.0 and s2 != 0.0 or s2 == 0.0 and s1 != 0.0:
        abort(400, 'Invalid SIZE (' + arg + '): degenerate region')
    return s1, s2

def _get_FORMAT(arg):
    """Extracts the value of the SIA FORMAT parameter.
    """
    if arg is None:
        return 'image/fits'
    elif arg == 'ALL':
        return 'image/fits'
    elif arg == 'METADATA':
        return arg
    elif arg.startswith('GRAPHIC'):
        abort(400, 'The GRAPHIC FORMAT is not supported by this service')
    elif arg != 'image/fits':
        abort(400, 'FORMAT must be one of ALL, image/fits or METADATA - got ' + arg)
    return arg

def _get_columns(columns, table):
    """Extracts the list of columns to retrieve.
    """
    cols = []
    if columns is None:
        # No column selection list specified
        cols = [c for c in table.iter(tag='principal')]
        if table.corners and table.corners.computed:
            cols.extend([c for c in table.corners])
    else:
        for c in columns.split(','):
            c = c.strip()
            if len(c) == 0:
                continue
            if c not in table:
                if not table.corners or not c in table.corners:
                    abort(400, ' '.join(['Column', c, 'does not exist in table', table.id()]))
                else:
                    cols.append(table.corners[c])
            elif not table[c].selectable:
                abort(400, ' '.join(['Column', c, 'in table', table.id(), 'is not selectable']))
            else:
                cols.append(table[c])
    return cols

def _get_writer_class(ct):
    if ct is None or ct in ('text/plain', 'text', 'ipac_table'):
        return formats.IpacAsciiWriter
    elif ct in ('text/csv', 'csv'):
        return formats.CsvWriter
    elif ct in ('text/tab-separated-values', 'tsv'):
        return formats.TsvWriter
    elif ct in ('text/html', 'html'):
        return formats.HtmlWriter
    else:
        abort(400, 'Requested output format ({0}) not supported'.format(ct))


_valid_params = set(['ct', 'format', 'pos', 'refby', 'size', 'intersect', 'columns', 'where', 'mcen',])
_valid_sia_params = set(['naxis', 'cframe', 'equinox', 'crpix', 'crval', 'cdelt', 'rotang', 'proj', 'verb']).union(_valid_params)

def _validate_params(params, sia=False):
    """Validates that there are no unexpected parameters, and returns a mapping of
    lowercase parameter names to the parameter names actually specified. This is used
    to provide case insensitivity.
    """
    map = dict()
    valid_set = _valid_sia_params if sia else _valid_params
    for k in params.iterkeys():
        lk = k.lower()
        if lk not in valid_set:
            abort(400, 'Parameter {0} is not recognized'.format(k))
        if len(params.getall(k)) > 1 or lk in map:
            abort(400, 'Parameter {0} was specified multiple times (note: parameters names are case insensitive)'.format(k))
        map[lk] = k
    for lk in _valid_params:
        if not lk in map:
            map[lk] = lk
    return map


# -- output utilities ----

def _empty_table(writer_class, table, columns, server=None, url_root=None):
    """Returns an empty table.
    """
    response.headers['Content-Type'] = writer_class.content_type()
    with closing(StringIO()) as output:
        with closing(writer_class(output, table, columns, server, url_root)) as writer:
            pass
        return output.getvalue()

def _metadata(writer_class, table):
    columns = []
    n = max(len(c.name) for c in table.iter('selectable'))
    columns.append(cat.Column(name='name', datatype='VARCHAR({0})'.format(n)))
    n = max(len(c.description or '') for c in table.iter('selectable'))
    columns.append(cat.Column(name='description', datatype='VARCHAR({0})'.format(n)))
    n = max(len(';'.join(c.ucds)) for c in table.iter('selectable'))
    columns.append(cat.Column(name='ucd', datatype='VARCHAR({0})'.format(n)))
    n = max(len(c.type.get(formats.ADQL)) for c in table.iter('selectable'))
    columns.append(cat.Column(name='datatype', datatype='VARCHAR({0})'.format(n)))
    columns.append(cat.Column(name='size', datatype='INTEGER'))
    n = max(len(c.type.get(formats.ASCII)) for c in table.iter('selectable'))
    columns.append(cat.Column(name='ascii_type', datatype='VARCHAR({0})'.format(n)))
    n = max(len(c.unit or '') for c in table.iter('selectable'))
    columns.append(cat.Column(name='unit', datatype='VARCHAR({0})'.format(n)))
    columns.append(cat.Column(name='nullable', datatype='INTEGER'))
    columns.append(cat.Column(name='principal', datatype='INTEGER'))
    columns.append(cat.Column(name='indexed', datatype='INTEGER'))
    columns.append(cat.Column(name='std', datatype='INTEGER'))
    response.headers['Content-Type'] = writer_class.content_type()
    with closing(StringIO()) as output:
        with closing(writer_class(output, None, columns)) as writer:
            for c in table:
                if not c.selectable:
                    continue
                datatype, size = c.type.get(formats.VOTABLE)
                if size is not None:
                    size = int(size[:-1] if size[-1] == '*' else size)
                writer.write({
                    'name': c.name,
                    'description' : c.description,
                    'ucd': ';'.join(c.ucds),
                    'datatype': datatype,
                    'size': size,
                    'ascii_type': c.type.get(formats.ASCII),
                    'unit': c.unit,
                    'nullable': int(c.nullable),
                    'principal': int(c.principal),
                    'indexed': int(c.indexed),
                    'std': int(c.std),
                }, None)
        return output.getvalue()


# -- Access control utilities ----

GROUP_ALL = -99 # group ID for the all-seeing users
GROUP_NONE = -1 # group ID for mission-wide public data
GROUP_ROW = 0   # indicates access checks must be performed per-row rather than per-table
MISSION_NONE = -1
MISSION_ALL = -99

def _get_groups(sessionId, sessionContext, missionId):
    groups = set()
    if sessionId is not None and sessionContext is not None:
        # extract user groups for mission
        s = ssoc.sso_getGroupStr(sessionContext, missionId)
        if sessionContext.status != 0:
            abort(500, str.format('Could not get group information: {0}, '
                'system error: {1}.', sessionContext.errorMsg,
                os.strerror(sessionContext.syserr)))
        groups = set(map(int, (g for g in s.split(','))) if s else [])
        if len(groups) > 0:
            # if the user belongs to any group for the mission, then the user
            # is allowed to see all data tagged as GROUP_NONE for that mission.
            groups.add(GROUP_NONE)
        # check if the user is listed as a "super-user" (allowed to access
        # anything), and if so include GROUP_ALL in the IDs returned.
        s = ssoc.sso_getGroupStr(sessionContext, MISSION_ALL)
        if GROUP_ALL in map(int, (i for i in s.split(','))) if s else []:
            groups.add(GROUP_ALL)
    return groups

def _date_restriction():
    return constraints.SqlLessThanPred((
        constraints.SqlColumnReference(["ipac_pub_date"]),
        constraints.SqlNow()))

def _gid_restriction(groups):
    values = constraints.SqlValueList(
        constraints.SqlNumericLiteral((str(g),)) for g in groups)
    return constraints.SqlInPred((
        constraints.SqlColumnReference(["ipac_gid"]),
        False,
        values))

def _access_restriction(sessionContext, sessionId, t):
    """Returns a SQL WHERE clause (in AST form) that implements access
    restrictions for the given table t. The running request is aborted with
    a 401 or 403 if the user does not have access to the given table at all.
    """
    policy = t.access.policy
    mission = t.access.mission
    group = t.access.group
    if ((mission == MISSION_NONE and group != GROUP_NONE) or
        (mission <= 0 and mission != MISSION_NONE)):
        abort(500, 'Invalid server configuration')
    if policy == 'ACCESS_DENIED':
        abort(403) # Nobody (not even an admin) can access the data
    elif policy == 'ACCESS_TABLE':
        if group == GROUP_ROW:
            abort(500, 'Invalid server configuration')
        elif mission != MISSION_NONE:
            groups = _get_groups(sessionId, sessionContext, mission)
            if not (group in groups or GROUP_ALL in groups):
                abort(401)
    elif policy == 'ACCESS_ROW_ONLY':
        if group != GROUP_ROW or mission == MISSION_NONE:
            abort(500, 'Invalid server configuration')
        groups = _get_groups(sessionId, sessionContext, mission)
        if len(groups) == 0:
            abort(401)
        elif GROUP_ALL not in groups:
            return _gid_restriction(groups)
    elif policy == 'ACCESS_DATE_ONLY':
        if group != GROUP_ROW:
            abort(500, 'Invalid server configuration')
        return _date_restriction()
    elif policy == 'ACCESS_ROW_DATE':
        if group != GROUP_ROW or mission == MISSION_NONE:
            abort(500, 'Invalid server configuration')
        groups = _get_groups(sessionId, sessionContext, mission)
        if len(groups) == 0:
            return _date_restriction()
        elif GROUP_ALL not in groups:
            return constraints.SqlOr((_gid_restriction(groups), _date_restriction()))
    elif policy != 'ACCESS_GRANTED':
        abort(500, 'Invalid server configuration')
    # no access restrictions
    return None


# -- Search controller implementation ----

class SearchController(BaseController):
    """Controller for searching image meta-data tables.
    """
    _vo_params = ('POS', 'SIZE', 'INTERSECT')
    _intersect = ('COVERS', 'ENCLOSED', 'CENTER', 'OVERLAPS')

    def search(self):
        """Performs a spatial and/or relational query using at most one
        spatial constraint (currently either a rectangular region or a point).
        """
        wsdir = None
        try:
            # get table for query
            t = h.resolve(*h.get_urlvars(('schema_group', 'schema', 'table')))
            # get session id from cookies
            sessionId = request.cookies.get(g.sso_session_id_env, None)
            # look up session context if necessary. Note: this is NOT thread-safe!
            sessionContext = None
            try:
                if (sessionId is not None and t.access.policy not in
                    ('ACCESS_GRANTED', 'ACCESS_DENIED', 'ACCESS_DATE_ONLY')):
                    sessionContext = ssoc.sso_openUsingSessionId(str(sessionId))
                    if sessionContext is not None and sessionContext.status != 0:
                        # There was a problem retrieving the session context,
                        # so treat the user as anonymous
                        sessionId = None
                # get security discriminator for WHERE clause
                security_where = _access_restriction(sessionContext, sessionId, t)
            finally:
                if sessionContext is not None:
                    ssoc.sso_close(sessionContext)
                sessionContext = None
            # get URL variables
            params = _validate_params(request.params)
            writer_class = _get_writer_class(request.params.get(params['ct'], None))
            format = _get_FORMAT(request.params.get(params['format'], None))
            if format == 'METADATA':
                return _metadata(writer_class, t)
            if t.wcsutils is None:
                abort(400, 'Table ' + t.id() +
                      ' is not an image metadata table and cannot be queried directly')
            # get main query parameters
            center = request.params.get(params['pos'], None)
            upload = False
            where = None
            if center is not None:
                if isinstance(center, basestring):
                    if '(' in center:
                        row = tableid.lookup_pos(*tableid.parse_id_spec(center))
                        if row is None:
                            abort(400, center + ' does not identify an existing row')
                        center = float(row[0]), float(row[1])
                    else:
                        center = _get_POS(center)
                else:
                    center = center.file
                    upload = True
            else:
                # No spatial constraint - may still be able to lookup values
                # based on a row from another table.
                where = _get_refby(request.params.get(params['refby'], None), t)
            s1, s2 = _get_SIZE(request.params.get(params['size'], None))
            intersect = request.params.get(params['intersect'], 'OVERLAPS')
            if intersect not in self._intersect:
                abort(400, 'INTERSECT must be one of ' + ', '.join(self._intersect))
            most_centered = params['mcen'] in request.params

            # get retrieval columns / user specified WHERE clause
            columns = _get_columns(request.params.get(params['columns'], None), t)
            where_clause = request.params.get(params['where'], None)
            if where_clause is not None:
                if len(where_clause.strip()) == 0:
                    abort(400, "Empty WHERE clause")
                # parse WHERE clause into an AST
                try:
                    w = g.parser(where_clause)[0]
                except Exception, ex:
                    abort(400, 'Invalid WHERE clause: ' + str(ex))
                # merge where clause with AST built from row reference
                where = w if where is None else constraints.SqlAnd((where, w))
                # Determine names of columns referenced by WHERE clause
                where_cols = where.extract_cols()
                for n in where_cols:
                    if not n in t:
                        abort(400, str.format('Table {0} does not contain a ' +
                            'column named {1}.', t.id(), n))
                    if not t[n].queryable:
                        abort(400, str.format('Column {0} in table {1} is not ' +
                            'allowed to participate in constraints', n, t.id()))

            # Basic sanity checks
            if center is None and where is None:
                abort(400, 'No spatial constraint (POS) or relational ' +
                    'constraint (where, refby) specified')
            if center is not None and (not t.corners or not t.chunk_index):
                abort(400, 'Table ' + t.id() + ' cannot be queried ' +
                    'spatially: missing corners and/or chunk index')

            # merge security discriminator with WHERE clause
            if security_where is not None:
                where = security_where if where is None else constraints.SqlAnd((where, security_where))
            # determine columns to retrieve
            dbnames = [c.dbname for c in columns if not (c.computed or c.constant)]
            # always retrieve WCS columns
            for c in t.wcsutils.columns:
                if not c.constant and not c.dbname in dbnames:
                    dbnames.append(c.dbname)
            # always retrieve corners and center, unless they are computed
            if not t.corners.computed:
                for c in t.corners:
                    if not c.constant and not c.dbname in dbnames:
                        dbnames.append(c.dbname)
            if not t.center.computed:
                for c in t.center:
                    if not c.constant and not c.dbname in dbnames:
                        dbnames.append(c.dbname)
            # if returning only the most centered image set, retrieve the columns
            # defining image set membership
            if most_centered:
                for n in t.image_set:
                    c = t[n]
                    if not c.constant and not c.dbname in dbnames:
                        dbnames.append(c.dbname)

            # create search region
            region = False
            if center is not None:
                search_rad = t.corners.radius
                if (s1 == s2 and s1 == 0.0) or (intersect == 'CENTER'):
                    # search region is a point
                    if intersect == 'ENCLOSED':
                        # no image is ever enclosed by a point
                        return _empty_table(writer_class, t, columns)
                else:
                    # search region is a rectangle
                    region = True
                    search_rad += math.sqrt(0.25*(s1**2 + s2**2))

                # verify that search radius is within reason
                if search_rad > t.chunk_index.max_radius:
                    max_bcr = t.chunk_index.max_radius - t.corners.radius
                    abort(400, 'Search region is too large - the maximum region ' +
                         'bounding circle radius is {0!r} deg'.format(max_bcr))

                # create workspace, write out table containing search center(s)
                wsdir = h.make_ws()
                pos_file = os.path.join(wsdir, 'pos.tbl')
                match_file = os.path.join(wsdir, 'match.tbl')
                if upload:
                    with open(pos_file, 'wb') as pf:
                        shutil.copyfileobj(center, pf)
                    center.close()
                else:
                    with open(pos_file, 'wb+') as f:
                        f.write('|{0:24}|{1:24}|\n'.format('ra', 'dec'))
                        f.write('|{0:24}|{0:24}|\n'.format('double'))
                        f.write('|{0:24}|{0:24}|\n'.format('deg'))
                        f.write('|{0:24}|{0:24}|\n'.format(''))
                        f.write(' {0[0]!r:24} {0[1]!r:24} \n'.format(center))

            # Perform search
            if center is None:
                # No spatial constraint specified
                response.headers['Content-Type'] = writer_class.content_type()
                return streamer.where_from_db(t, where, dbnames, columns, writer_class)
            else:
                # Have a spatial constraint - use chunk index.
                assoc_args = ['assoc', '-j', '-q',
                              '-t', pos_file, '-I',
                              '-T', match_file,
                              '-i', t.chunk_index.path,
                              '-M', repr(search_rad) + ' deg',
                              '-C', ','.join(dbnames),
                              '-r', 'row_id',
                              '-c', '*',
                              '-p', 'in_',
                             ]
                if where is not None:
                    assoc_args.extend(['-w', where.render(t)])
                results = json.loads(utils.call(assoc_args))
                if results['stat'] != 'OK':
                    abort(500, results['msg'])
                if int(results['props']['num-recorded-matches']) == 0:
                    return _empty_table(writer_class, t, streamer.input_cols(match_file) + columns)

                # Stream back results
                response.headers['Content-Type'] = writer_class.content_type()
                if region:
                    return streamer.reg_from_ipac(wsdir, match_file, t, dbnames,
                                                  s1, s2, intersect,
                                                  columns, writer_class)
                elif most_centered:
                    return streamer.mcen_from_ipac(wsdir, match_file, t, dbnames,
                                                   columns, writer_class)
                else:
                    return streamer.point_from_ipac(wsdir, match_file, t, dbnames,
                                                    columns, writer_class)

        except HTTPException, ex:
            if wsdir is not None:
                with utils.Swallow(): shutil.rmtree(wsdir)
            raise ex
        except Exception, ex:
            with utils.Swallow(): log.error(traceback.format_exc())
            if wsdir is not None:
                with utils.Swallow(): shutil.rmtree(wsdir)
            abort(500, str(ex))

    def sia(self):
        """Performs a SIA spatial query.
        """
        err_msg = ''
        wsdir = None
        response.headers['Content-Type'] = 'application/x-votable+xml; charset=UTF-8'
        try:
            # get URL variables
            t = h.resolve(*h.get_urlvars(('schema_group', 'schema', 'table')))
            # get session id from cookies
            sessionId = request.cookies.get(g.sso_session_id_env, None)
            # look up session context if necessary. Note: this is NOT thread-safe!
            sessionContext = None
            try:
                if (sessionId is not None and t.access.policy not in
                    ('ACCESS_GRANTED', 'ACCESS_DENIED', 'ACCESS_DATE_ONLY')):
                    sessionContext = ssoc.sso_openUsingSessionId(str(sessionId))
                    if sessionContext is not None and sessionContext.status != 0:
                        # There was a problem retrieving the session context,
                        # so treat the user as anonymous
                        sessionId = None
                # get security discriminator for WHERE clause
                security_where = _access_restriction(sessionContext, sessionId, t)
            finally:
                if sessionContext is not None:
                    ssoc.sso_close(sessionContext)
                sessionContext = None

            if not t.corners or not t.chunk_index:
                abort(400, 'Table ' + t.id() + ' cannot be queried ' +
                    'spatially: missing corners and/or chunk index')
            params = _validate_params(request.params, sia=True)
            writer_class = t.sia_writer_class
            if writer_class is None:
                abort(400, 'VO SIA support for table ' + t.id() +
                      ' is not currently available')
            # get retrieval columns
            columns = writer_class.get_required_cols(t)
            # get format
            format = _get_FORMAT(request.params.get(params['format'], None))
            if format == 'METADATA':
                return _empty_table(writer_class, t, columns, g.server, g.url_root)
            # get main query parameters
            center = request.params.get(params['pos'], None)
            if center is None or not isinstance(center, basestring):
                abort(400, 'POS not specified')
            center = _get_POS(center)
            s1, s2 = _get_SIZE(request.params.get(params['size'], None))
            intersect = request.params.get(params['intersect'], 'OVERLAPS')
            if intersect not in self._intersect:
                abort(400, 'INTERSECT must be one of ' + ', '.join(self._intersect))
            most_centered = params['mcen'] in request.params

            # determine columns to retrieve
            dbnames = [c.dbname for c in columns if not (c.computed or c.constant)]
            # always retrieve WCS columns
            for c in t.wcsutils.columns:
                if not c.constant and not c.dbname in dbnames:
                    dbnames.append(c.dbname)
            # always retrieve corners and center, unless they are computed
            if not t.corners.computed:
                for c in t.corners:
                    if not c.constant and not c.dbname in dbnames:
                        dbnames.append(c.dbname)
            if not t.center.computed:
                for c in t.center:
                    if not c.constant and not c.dbname in dbnames:
                        dbnames.append(c.dbname)
            # if returning only the most centered image set, retrieve the columns
            # defining image set membership
            if most_centered:
                for n in t.image_set:
                    c = t[n]
                    if not c.constant and not c.dbname in dbnames:
                        dbnames.append(c.dbname)
            # create search region
            region = False
            search_rad = t.corners.radius
            if (s1 == s2 and s1 == 0.0) or (intersect == 'CENTER'):
                # search region is a point
                if intersect == 'ENCLOSED':
                    # no image is ever enclosed by a point
                    return _empty_table(writer_class, t, columns, g.server, g.url_root)
            else:
                # search region is a rectangle
                region = True
                search_rad += math.sqrt(0.25*(s1**2 + s2**2))

            # verify that search radius is within reason
            if search_rad > t.chunk_index.max_radius:
                max_bcr = t.chunk_index.max_radius - t.corners.radius
                abort(400, 'Search region is too large - the maximum region ' +
                     'bounding circle radius is {0!r} deg'.format(max_bcr))

            # create workspace, write out table containing search center(s)
            wsdir = h.make_ws()
            pos_file = os.path.join(wsdir, 'pos.tbl')
            match_file = os.path.join(wsdir, 'match.tbl')
            with open(pos_file, 'wb+') as f:
                f.write('|{0:24}|{1:24}|\n'.format('ra', 'dec'))
                f.write('|{0:24}|{0:24}|\n'.format('double'))
                f.write('|{0:24}|{0:24}|\n'.format('deg'))
                f.write('|{0:24}|{0:24}|\n'.format(''))
                f.write(' {0[0]!r:24} {0[1]!r:24} \n'.format(center))

            # Apply rough spatial constraint via the chunk index
            assoc_args = ['assoc', '-j', '-q',
                          '-t', pos_file, '-I',
                          '-T', match_file,
                          '-i', t.chunk_index.path,
                          '-M', repr(search_rad) + ' deg',
                          '-C', ','.join(dbnames),
                          '-r', 'in_row_id',
                          '-c', 'in_row_id, ra AS in_ra, dec AS in_dec'
                         ]
            if security_where is not None:
                    assoc_args.extend(['-w', security_where.render(t)])
            results = json.loads(utils.call(assoc_args))
            if results['stat'] != 'OK':
                abort(500, results['msg'])
            if int(results['props']['num-recorded-matches']) == 0:
                return _empty_table(writer_class, t, columns, g.server, g.url_root)

            # Stream back results
            if region:
                return streamer.reg_from_ipac(wsdir, match_file, t, dbnames,
                                              s1, s2, intersect, columns,
                                              writer_class, g.server, g.url_root)
            elif most_centered:
                return streamer.mcen_from_ipac(wsdir, match_file, t, dbnames, columns,
                                               writer_class, g.server, g.url_root)
            else:
                return streamer.point_from_ipac(wsdir, match_file, t, dbnames, columns,
                                                writer_class, g.server, g.url_root)

        except HTTPException, ex:
            if wsdir is not None:
                with utils.Swallow(): shutil.rmtree(wsdir)
            err_msg = ''.join([ex.explanation, '\n', ex.detail])
        except Exception, ex:
            with utils.Swallow(): log.error(traceback.format_exc())
            if wsdir is not None:
                with utils.Swallow(): shutil.rmtree(wsdir)
            err_msg = str(ex)
        return '''\
<?xml version="1.0"?>
<VOTABLE version="1.2"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xmlns="http://www.ivoa.net/xml/VOTable/v1.2" >
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="ERROR"><![CDATA[

%s

]]></INFO></RESOURCE>
</VOTABLE>
''' % err_msg


