from contextlib import closing, nested
from cStringIO import StringIO
import shutil

import sqlalchemy as sa

import ibe.lib.ascii_table as ascii_table
import ibe.lib.catalogs as catalogs
import ibe.lib.geom as geom
import ibe.lib.formats as formats
import ibe.lib.helpers as helpers
import ibe.lib.utils as utils
import ibe.lib.types as types


# -- Helper methods --------

def _corners2poly(corners):
    """Returns a polygon with vertices given by an array of 4
    2-float tuples. Vertices may be in either clockwise or
    counter-clockwise order.
    """
    verts = map(geom.unitVector, corners)
    n = geom.cross(verts[0], verts[1])
    if geom.dot(n, verts[2]) < 0.0:
        verts.reverse()
    return geom.SphericalConvexPolygon(verts)

def _row2poly(corner_names, row):
    """Returns a polygon from corner coordinates specified in a table row.
    """
    return _corners2poly(((row[corner_names[0]], row[corner_names[1]]),
                          (row[corner_names[2]], row[corner_names[3]]),
                          (row[corner_names[4]], row[corner_names[5]]),
                          (row[corner_names[6]], row[corner_names[7]])))

def _edge_dist(table, row, point):
    """Computes the minimum (pixel) distance of point to an image edge.
    Returns this minimum distance and a WCS for the image corresponding
    to row.
    """
    wcs = table.wcsutils.makeWcs(row)
    pix = wcs.wcs_sky2pix([point], 1)[0]
    xmax = table.wcsutils.naxis1.get(row) + 0.5
    ymax = table.wcsutils.naxis2.get(row) + 0.5
    if (pix[0] <= 0.5 or pix[1] <= 0.5 or
        pix[0] >= xmax or pix[1] >= ymax):
        return -1.0, None
    return min(pix[0] - 0.5, pix[1] - 0.5, xmax - pix[0], ymax - pix[1]), wcs

def input_cols(input):
    if not isinstance(input, ascii_table.Reader):
        input = ascii_table.Reader(input)
    cols = []
    for c in input.columns():
        if not c.name.startswith("in_"):
            continue;
        cols.append(catalogs.Column(
            name=c.name,
            unit=c.units,
            type=types.from_ascii(c.type, c.end - c.begin, None, c.null)
        ))
    return cols


class _MCenFinder(object):
    def __init__(self, table):
        if table.image_set is not None and len(table.image_set) > 0:
            self.image_set = list(table[c].dbname for c in table.image_set)
        else:
            self.image_set = None
        self.reset()

    def reset(self):
        self.mcen_row = None
        self.mcen_wcs = None
        self.mm_edge_dist = -1.0
        self.rows = {}

    def add_row(self, table, row, point):
        edge_dist, wcs = _edge_dist(table, row, point)
        if edge_dist > self.mm_edge_dist:
            self.mcen_row = row
            self.mcen_wcs = wcs
            self.mm_edge_dist = edge_dist
        if self.image_set:
            cs = tuple(row[c] for c in self.image_set)
            if cs in self.rows:
                self.rows[cs].append((row, wcs))
            else:
                self.rows[cs] = [(row, wcs)]

    def flush(self, table, writer):
        if self.mcen_row is None:
            self.reset()
            return 0
        n_rows = 0
        if self.image_set:
            cs = tuple(self.mcen_row[c] for c in self.image_set)
            rows = self.rows[cs]
        else:
            rows = [(self.mcen_row, self.mcen_wcs)]
        for row, wcs in rows:
            writer.write(row, table.compute_row(row, wcs))
            n_rows += 1
        self.reset()
        return n_rows


# -- Streaming back results from IPAC ASCII files --------

def make_reader(matchfile, table):
    reader = ascii_table.Reader(matchfile)
    for c in table:
        if c.dbname in reader and isinstance(c.type, (types.Time, types.Date, types.DateTime)):
            t = c.type
            reader.column(c.dbname).value = lambda x: t.to_python(x)
    return reader

def reg_from_ipac(wsdir, match_file, table, dbnames,
                  size1, size2, intersect, columns, writer_class,
                  server=None, url_root=None):
    """Given a region and match file (containing candidate overlaps
    with region), stream back the rows satisfying the spatial predicate
    (specified via intersect).
    """
    try:
        mask = 1024 - 1 # operate on 1024 rows at a time
        n_rows = 0
        compute_corners = table.corners.computed
        cnames = [c.dbname for c in table.corners]

        with nested(
            closing(make_reader(match_file, table)),
            closing(StringIO())
        ) as (reader, output):

            with writer_class(output, table, input_cols(reader) + columns, server, url_root) as writer:

                yield output.getvalue()
                output.truncate(0)
                in_row_id = None

                for row in reader:
                    if row['in_row_id'] != in_row_id:
                        in_row_id = row['in_row_id']
                        region = geom.make_rectangle(float(row['in_ra']),
                                                     float(row['in_dec']),
                                                     size1, size2)
                    computed_row = table.compute_row(row)
                    if compute_corners:
                        poly = _row2poly(cnames, computed_row)
                    else:
                        poly = _row2poly(cnames, row)
                    if intersect == 'OVERLAPS':
                        ok = poly.intersects(region)
                    elif intersect == 'COVERS':
                        ok = poly.contains(region)
                    else:
                        ok = region.contains(poly)
                    if not ok:
                        continue
                    n_rows += 1
                    writer.write(row, computed_row)
                    if (n_rows & mask) == 0 and output.tell() != 0:
                        yield output.getvalue()
                        output.truncate(0)
            if output.tell() != 0:
                yield output.getvalue()

    finally:
        # clean-up workspace
        with utils.Swallow(): shutil.rmtree(wsdir)


def point_from_ipac(wsdir, match_file, table, dbnames,
                    columns, writer_class, server=None, url_root=None):
    """Given a point and match file (containing candidate overlaps
    with point), stream back the rows that contain point.
    """
    try:
        mask = 1024 - 1 # operate on 1024 rows at a time
        n_rows = 0

        with nested(
            closing(make_reader(match_file, table)),
            closing(StringIO())
        ) as (reader, output):

            with writer_class(output, table, input_cols(reader) + columns, server, url_root) as writer:

                yield output.getvalue()
                output.truncate(0)
                in_row_id = None
                for row in reader:
                    if row['in_row_id'] != in_row_id:
                        in_row_id = row['in_row_id']
                        point = (float(row['in_ra']), float(row['in_dec']))
                    wcs = table.wcsutils.makeWcs(row)
                    computed_row = table.compute_row(row, wcs)
                    pix = wcs.wcs_sky2pix([point], 1)[0]
                    if (pix[0] <= 0.5 or pix[1] <= 0.5 or
                        pix[0] >= table.wcsutils.naxis1.get(row) + 0.5 or
                        pix[1] >= table.wcsutils.naxis2.get(row) + 0.5):
                        continue
                    n_rows += 1
                    writer.write(row, computed_row)
                    if (n_rows & mask) == 0 and output.tell() != 0:
                        yield output.getvalue()
                        output.truncate(0)
            if output.tell() != 0:
                yield output.getvalue()

    finally:
        with utils.Swallow(): shutil.rmtree(wsdir)


def mcen_from_ipac(wsdir, match_file, table, dbnames,
                   columns, writer_class, server=None, url_root=None):
    """Given a point and match file (containing candidate overlaps
    with point), return the rows corresponding to the most centered
    image-set containing the point.
    """
    try:
        mask = 1024 - 1 # operate on 1024 rows at a time
        n = 0
        finder = _MCenFinder(table)

        # execute query and stream back results
        with nested(
            closing(make_reader(match_file, table)),
            closing(StringIO()),
        ) as (reader, output):

            with writer_class(output, table, input_cols(reader) + columns, server, url_root) as writer:

                yield output.getvalue()
                output.truncate(0)
                in_row_id = None
                n_rows = 0

                for row in reader:
                    if row['in_row_id'] != in_row_id:
                        nw = finder.flush(table, writer)
                        if (n_rows & mask) + nw > mask and output.tell() != 0:
                            yield output.getvalue()
                            output.truncate(0)
                        n_rows += nw
                        in_row_id = row['in_row_id']
                        point = (float(row['in_ra']), float(row['in_dec']))
                    finder.add_row(table, row, point)
                finder.flush(table, writer)

            if output.tell() != 0:
                yield output.getvalue()
                output.truncate(0)

    finally:
        with utils.Swallow(): shutil.rmtree(wsdir)


# -- Streaming back results from a database table --------

def where_from_db(table, where, dbnames, columns, writer_class,
                  server=None, url_root=None):
    """Streams back the results of running the specified query
    on the given table.
    """
    mask = 1024 - 1 # operate on 1024 rows at a time
    n_rows = 0
    sa_table = table.table()
    stmt = sa.select([sa_table.c[n] for n in dbnames]).where(where.build(table, sa_table))

    with nested(
        closing(StringIO()),
        closing(table.engine.connect())
    ) as (output, conn):

        with nested(
            writer_class(output, table, columns, server, url_root),
            closing(conn.execute(stmt))
        ) as (writer, rows):

            yield output.getvalue()
            output.truncate(0)

            for row in rows:
                computed_row = table.compute_row(row)
                writer.write(row, computed_row)
                n_rows += 1
                if (n_rows & mask) == 0 and output.tell() != 0:
                    yield output.getvalue()
                    output.truncate(0)
        if output.tell() != 0:
            yield output.getvalue()

