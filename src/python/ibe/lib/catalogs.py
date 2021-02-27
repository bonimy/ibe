import collections
import lxml.etree as etree
from itertools import izip
import json
import numpy
import os.path
import pdb
import pywcs
import re
import sqlalchemy as sa
import sys

import ibe.lib.formats as formats
import ibe.lib.geom as geom
import ibe.lib.types as types
import ibe.lib.utils as utils


# -- Helper functions --------

def _wcs_col(table, cset, fits_key, ucd, utype):
    s = table.find(ucd, utype)
    if len(s) != 1:
        raise RuntimeError(str.format('Expecting exactly 1 column ' +
            'corresponding to {0} FITS WCS keyword, got {1}',
            fits_key, ','.join(c.dbname for c in s)))
    c = s.pop()
    cset.add(c)
    return c


# -- Classes --------

class ChunkIndex(object):
    """Stores the path to, maximum search radius of, and column names
    in a chunk index file. The following attributes are available:

    - path:       The path to the chunk index file.
    - max_radius: The maximum search radius (deg) supported by the
                  chunk index.
    - columns:    A list of database column names available in the
                  chunk index.
    - types:      A list of column types.
    """
    def __init__(self, element):
        self.path = element.get('path')
        if self.path is None:
            raise RuntimeError('chunk_index element must have a path attribute')
        if not os.path.isfile(self.path):
            raise RuntimeError(str.format(
                'chunk index path {0} does not exist or is not a file', self.path))
        props = json.loads(utils.call(['ci_info', '-j', '-i', self.path]))
        self.max_radius = props['overlapDeg']
        cols = props['columns']
        self.columns = [None] * len(cols)
        self.types = [None] * len(cols)
        for name in cols:
            i = cols[name]['index']
            if self.columns[i] is not None:
                raise RuntimeError(str.format('chunk index {0} contains ' +
                    'two columns ({1}, {2}) with the same index ({3})',
                    self.path, self.columns[i], name, i))
            self.columns[i] = name
            self.types[i] = str(cols[name]['type'])
        self._cset = set(self.columns)

    def __contains__(self, key):
        return key in self._cset


class Corners(collections.Mapping):
    """The logical column names corresponding to the FK5 J2000 positions
    of the 4 corners of an image in a table. These must be in clockwise or
    counter-clockwise order (no bow-ties), which avoids having to compute
    their convex hull during spatial searches. The following attributes
    are available:

    - radius:   Bounding circle radius (deg) for images in the table.
    - computed: True if column values must be computed, False if they are
                stored in the table.
    """
    _corner_cols = ('ra1', 'dec1', 'ra2', 'dec2', 'ra3', 'dec3', 'ra4', 'dec4')

    def __init__(self, element, table):
        radius = element.get('radius')
        if radius is None:
            raise RuntimeError('corners must have a radius attribute')
        self.radius = float(radius)
        cols = [element.get(c) or c for c in Corners._corner_cols]
        if all(c in table for c in cols):
            self.computed = False
            self._columns = [table[c] for c in cols]
        elif any(c in table for c in cols):
            raise RuntimeError(str.format(
                'table {0}: all corner columns must be stored or computed',
                table.id()))
        else:
            self.computed = True
            kwargs = { 'computed':   True,
                       'selectable': True,
                       'principal':  True,
                       'queryable':  False,
                       'nullable':   False,
                       'indexed':    False,
                       'unit':       'deg',
                       'datatype':   'DECIMAL(15,12)' }
            self._columns = []
            for i, name in enumerate(Corners._corner_cols):
                kwargs['name'] = name
                kwargs['ucd'] = ['pos.eq.ra'] if (i & 1) == 0 else ['pos.eq.dec']
                self._columns.append(Column(**kwargs))
        self._name_to_col = {}
        for c in self._columns:
            self._name_to_col[c.name] = c

    def __getitem__(self, key):
        """Retrieves the corner column with the specified logical name.
        """
        if isinstance(key, Column):
            return self._name_to_col[key.name]
        else:
            return self._name_to_col[key]

    def __contains__(self, key):
        """Tests whether or not a corner column with the specified logical name exists.
        """
        if isinstance(key, Column):
            return key.name in self._name_to_col
        else:
            return key in self._name_to_col

    def __iter__(self):
        """Returns an iterator over the corner columns.
        """
        return self._columns.__iter__()

    def __len__(self):
        """Returns the number of corner columns.
        """
        return len(self._columns)


class Center(collections.Mapping):
    """The logical column names corresponding to the FK5 J2000 position
    of the center of an image in a table.

    - computed: True if column values must be computed, False if they are
                stored in the table.
    """
    _center_cols = ('ra', 'dec')

    def __init__(self, element, table):
        if element is None:
            cols = Center._center_cols
        else:
            cols = [element.get(c) or c for c in Center._center_cols]
        if all(c in table for c in cols):
            self.computed = False
            self.columns = [table[c] for c in cols]
        elif any(c in table for c in cols):
            raise RuntimeError(str.format(
                'table {0}: all center columns must be stored or computed',
                table.id()))
        else:
            self.computed = True
            kwargs = { 'computed':   True,
                       'selectable': True,
                       'principal':  True,
                       'queryable':  False,
                       'nullable':   False,
                       'indexed':    False,
                       'unit':       'deg',
                       'datatype':   'DECIMAL(15,12)' }
            self.columns = []
            for i, name in enumerate(Center._center_cols):
                kwargs['name'] = name
                kwargs['ucd'] = ['pos.eq.ra'] if (i & 1) == 0 else ['pos.eq.dec']
                self.columns.append(Column(**kwargs))
        self._name_to_col = {}
        for c in self.columns:
            self._name_to_col[c.name] = c

    def __getitem__(self, key):
        """Retrieves the center column with the specified logical name.
        """
        if isinstance(key, Column):
            return self._name_to_col[key.name]
        else:
            return self._name_to_col[key]

    def __contains__(self, key):
        """Tests whether or not a center column with the specified logical name exists.
        """
        if isinstance(key, Column):
            return key.name in self._name_to_col
        else:
            return key in self._name_to_col

    def __iter__(self):
        """Returns an iterator over the center columns.
        """
        return self.columns.__iter__()

    def __len__(self):
        """Returns the number of center columns.
        """
        return len(self.columns)


class Products(object):
    """Identifies the file system path to data products associated with a table.
    """
    def __init__(self, element):
        self.rootpath = element.get('rootpath')


class Access(object):
    """Identifies the access type for a table.
    """
    def __init__(self, element=None):
        self.policy = element.get('policy', 'ACCESS_GRANTED') if element is not None else 'ACCESS_GRANTED'
        self.mission = int(element.get('mission', '-1')) if element is not None else -1
        self.group = int(element.get('group', '-1')) if element is not None else -1


class Column(collections.Hashable):
    """A column in a database table. Contains the following attributes:

    - name:        Logical column name.
    - dbname:      Database column name.
    - selectable:  True if the column can be selected.
    - nullable:    True if the column can contain NULLs.
    - principal:   True if the column should be returned for queries
                   that don't explicitly specify which columns to return.
    - queryable:   True if the column can be queried on.
    - indexed:     True if the column is indexed.
    - computed:    True if the column is computed.
    - constant:    True if the column is constant.
    - const_val:   Column value for contant columns or None.
    - std:         True if the column is defined by some external standard.
    - description: A short column description.
    - ucds:        A list of UCDs for the column.
    - utypes:      A list of UTYPEs for the column.
    - xtype:       The xtype of the column.
    - unit:        A column unit string.
    - type:        the ADQL type of the column.
    """
    reserved_names = set(['controller',
                          'action',
                          'schema_group',
                          'schema',
                          'table'])

    def __init__(self, **kwargs):
        self.name = kwargs.get('name', None)
        if (self.name is None or not isinstance(self.name, basestring) or
            len(self.name) == 0):
            raise RuntimeError('column has no name')
        if self.name in Column.reserved_names:
            raise RuntimeError(str.format(
                'column name {0} is reserved for internal use',
                self.name))
        if 'type' in kwargs:
            self.type = kwargs['type']
        else:
            dt = kwargs.get('datatype', None)
            if dt is None or not isinstance(dt, basestring) or len(dt) == 0:
                raise RuntimeError(str.format('column {0}{1} has no datatype',
                    kwargs.get('table', ''), self.name))
            self.type = types.from_adql(dt, kwargs.get('format_spec', None),
                                        kwargs.get('null_value', 'null'))
        self.dbname = kwargs.get('dbname', None) or self.name
        self.selectable = kwargs.get('selectable', True)
        self.principal = kwargs.get('principal', False)
        self.queryable = kwargs.get('queryable', self.selectable)
        if (self.queryable or self.principal) and not self.selectable:
            raise RuntimeError(str.format(
                'Column {0}{1} is principal or queryable, but not selectable',
                kwargs.get('table', ''), self.name))
        self.nullable = kwargs.get('nullable', False)
        self.indexed = kwargs.get('indexed', False)
        self.std = kwargs.get('std', False)
        self.computed = kwargs.get('computed', False)
        self.constant = 'constant' in kwargs
        if self.constant:
            if self.selectable or self.queryable:
                 raise RuntimeError(str.format(
                    'Column {0}{1} is constant, but also queryable or '
                    'selectable', kwargs.get('table', ''), self.name))
            self.const_val = self.type.to_python(kwargs['constant'])
        self.description = kwargs.get('description', None)
        self.ucds = kwargs.get('ucd', [])
        self.utypes = kwargs.get('utype', [])
        self.xtype = kwargs.get('xtype', None)
        self.unit = kwargs.get('unit', None)
        self._sa_column = None

    @staticmethod
    def from_element(element, prefix):
        # attributes
        kwargs = {}
        kwargs['computed'] = False
        kwargs['name'] = element.get('name')
        kwargs['dbname'] = element.get('dbname')
        kwargs['selectable'] = utils.xs_bool(element.get('selectable'), True)
        kwargs['principal'] = utils.xs_bool(element.get('principal'))
        kwargs['indexed'] = utils.xs_bool(element.get('indexed'))
        kwargs['std'] = utils.xs_bool(element.get('std'))
        # elements
        for tag in ('description', 'constant', 'xtype', 'unit',
                    'null_value', 'datatype', 'format_spec'):
            elt = element.find(tag)
            if elt is not None:
                kwargs[tag] = elt.text
        elt = element.find('ucd')
        if elt is not None:
            kwargs['ucd'] = [u.strip() for u in elt.text.split(';')]
        elt = element.find('utype')
        if elt is not None:
            kwargs['utype'] = [u.strip() for u in elt.text.split(';')]
        kwargs['table'] = prefix
        return Column(**kwargs)

    def column(self):
        """Returns the sqlalchemy Column object for this column. None
        for computed columns.
        """
        return self._sa_column

    def __hash__(self):
        return self.name.__hash__()

    def __eq__(self, other):
        if isinstance(other, Column):
            return self.name == other.name
        return False

    def get(self, row):
        return row[self.dbname] if not self.constant else self.const_val


class WcsUtils(object):
    """An object which can create pywcs.Wcs objects from table rows as
    well as compute image corners and center.
    """
    def __init__(self, table):
        if not isinstance(table, Table):
            raise TypeError(str.format('expecting a {0}.{1}, got a {2}.{3}',
                Table.__module__, Table.__name__, type(table).__module__,
                type(table).__name__))
        # Note that for now we assume EQUINOX=2000.0 and RADESYS='FK5', or
        # RADESYS='ICRS' (which are treated as identical).
        s = set()
        self.ctype1 = _wcs_col(table, s, 'CTYPE1', None, 'fits:CTYPE1')
        self.ctype2 = _wcs_col(table, s, 'CTYPE2', None, 'fits:CTYPE2')
        self.naxis1 = _wcs_col(table, s, 'NAXIS1', None, 'fits:NAXIS1')
        self.naxis2 = _wcs_col(table, s, 'NAXIS2', None, 'fits:NAXIS2')
        self.crpix1 = _wcs_col(table, s, 'CRPIX1', None, 'fits:CRPIX1')
        self.crpix2 = _wcs_col(table, s, 'CRPIX2', None, 'fits:CRPIX2')
        self.crval1 = _wcs_col(table, s, 'CRVAL1', None, 'fits:CRVAL1')
        self.crval2 = _wcs_col(table, s, 'CRVAL2', None, 'fits:CRVAL2')
        self.have_cd = False
        self.have_pc = False
        self.have_rot = False
        cs = table.find(None, 'fits:CD1_1')
        if len(cs) == 1:
            # Have a CD matrix
            self.have_cd = True
            self.cd1_1 = _wcs_col(table, s, 'CD1_1', None, 'fits:CD1_1')
            self.cd1_2 = _wcs_col(table, s, 'CD1_2', None, 'fits:CD1_2')
            self.cd2_1 = _wcs_col(table, s, 'CD2_1', None, 'fits:CD2_1')
            self.cd2_2 = _wcs_col(table, s, 'CD2_2', None, 'fits:CD2_2')
        else:
            # Must have scaling parameters
            self.cdelt1 = _wcs_col(table, s, 'CDELT1', None, 'fits:CDELT1')
            self.cdelt2 = _wcs_col(table, s, 'CDELT2', None, 'fits:CDELT2')
            if len(table.find(None, 'fits:PC1_1')) == 1:
                self.have_pc = True
                self.pc1_1 = _wcs_col(table, s, 'PC1_1', None, 'fits:PC1_1')
                self.pc1_2 = _wcs_col(table, s, 'PC1_2', None, 'fits:PC1_2')
                self.pc2_1 = _wcs_col(table, s, 'PC2_1', None, 'fits:PC2_1')
                self.pc2_2 = _wcs_col(table, s, 'PC2_2', None, 'fits:PC2_2')
            elif len(table.find(None, 'fits:CROTA2')) == 1:
                # Have a rotation
                self.have_rot = True
                self.crota2 = _wcs_col(table, s, 'CROTA2', None, 'fits:CROTA2')
        # record columns needed to construct a WCS
        self.columns = s

    def makeWcs(self, row):
        """Returns a pywcs.WCS using WCS parameters from the specified table row.
        """
        transform = pywcs.WCS()
        transform.wcs.ctype[0] = self.ctype1.get(row)
        transform.wcs.ctype[1] = self.ctype2.get(row)
        transform.wcs.crval = [float(self.crval1.get(row)), float(self.crval2.get(row))]
        transform.wcs.crpix = [float(self.crpix1.get(row)), float(self.crpix2.get(row))]
        if self.have_cd:
            cd = numpy.zeros(shape=(2,2), dtype=numpy.float64)
            cd[0,0] = float(self.cd1_1.get(row))
            cd[0,1] = float(self.cd1_2.get(row))
            cd[1,0] = float(self.cd2_1.get(row))
            cd[1,1] = float(self.cd2_2.get(row))
            transform.wcs.cd = cd
        elif self.have_pc:
            del transform.wcs.cd
            pc = numpy.zeros(shape=(2,2), dtype=numpy.float64)
            transform.cdelt = [float(self.cdelt1.get(row)), float(self.cdelt2.get(row))]
            pc[0,0] = float(self.pc1_1.get(row))
            pc[0,1] = float(self.pc1_2.get(row))
            pc[1,0] = float(self.pc2_1.get(row))
            pc[1,1] = float(self.pc2_2.get(row))
            transform.wcs.pc = pc
        else:
            del transform.wcs.cd
            crota = [0.0, 0.0]
            if self.have_rot:
                crota[1] = float(self.crota2.get(row))
            transform.wcs.cdelt = [float(self.cdelt1.get(row)), float(self.cdelt2.get(row))]
            transform.wcs.crota = crota
        transform.wcs.set()
        return transform

    def corners(self, row, wcs):
        """Returns an array of 4 2-float tuples corresponding to the
        sky coordinates of the image corners for a given table row.
        """
        naxis1 = float(self.naxis1.get(row))
        naxis2 = float(self.naxis2.get(row))
        v = numpy.zeros(shape=(4,2), dtype=numpy.float64)
        v[0,0] = 0.5
        v[0,1] = 0.5
        v[1,0] = 0.5 + naxis1
        v[1,1] = 0.5
        v[2,0] = 0.5 + naxis1
        v[2,1] = 0.5 + naxis2
        v[3,0] = 0.5
        v[3,1] = 0.5 + naxis2
        return wcs.all_pix2sky(v, 1)

    def center(self, row, wcs):
        """Returns a 2-float tuple corresponding to the
        sky coordinates of the image center for a given table row.
        """
        v = numpy.zeros(shape=(1,2), dtype=numpy.float64)
        v[0,0] = float(self.naxis1.get(row))*0.5 + 0.5
        v[0,1] = float(self.naxis2.get(row))*0.5 + 0.5
        return wcs.all_pix2sky(v, 1)[0]


class Table(collections.Mapping):
    """An immutable description of a database table.

    This is primarily represented as a mapping from logical column names to
    Column objects. Additionally, columns can be located by their database
    name, or by some combination of a list of UCDs or UTYPEs (the latter
    are defined by the IVOA, see http://www.ivoa.net for details).
    """
    def __init__(self, element, schema, engines):
        self.schema = schema

        # attributes
        self.name = element.get('name')
        self.dbname = element.get('dbname')
        if self.name is None or self.dbname is None:
            raise RuntimeError('table must have name and dbname attributes')
        engine = element.get("engine")
        if engine is None:
            if schema.engine is None:
                raise RuntimeError('No engine specified for table {0}'.format(self.id()))
            engine = schema.engine
        else:
            if engine not in engines:
                raise KeyError('"{0}" is not a valid engine ID'.format(engine))
            engine = engines[engine]
        self.engine = engine

        # elements
        elt = element.find('description')
        self.description = elt.text if elt is not None else None
        elt = element.find('chunk_index')
        self.chunk_index = ChunkIndex(elt) if elt is not None else None
        self.access = Access(element.find('access'))

        #TODO: deal with constant columns properly
        # Read in column descriptions
        self._cols = []
        self._name_to_col = {}
        self._dbname_to_col = {}
        self._ucd_to_cols = {}
        self._utype_to_cols = {}
        for child in element.iterchildren(tag='column'):
            col = Column.from_element(child, self.id() + '.')
            if col.name in self._name_to_col:
                raise RuntimeError(str.format(
                    'Duplicate definition for column {0}.{1}',
                    self.id(), col.name))
            if not col.constant and col.dbname in self._dbname_to_col:
                raise RuntimeError(str.format(
                    'Table {1} refers to database column {0} more than once',
                    col.dbname, self.id()))
            self._cols.append(col)
            self._name_to_col[col.name] = col
            if not col.constant:
                self._dbname_to_col[col.dbname] = col
            for ucd in col.ucds:
                if ucd in self._ucd_to_cols:
                    self._ucd_to_cols[ucd].add(col)
                else:
                    self._ucd_to_cols[ucd] = set((col,))
            for utype in col.utypes:
                if utype in self._utype_to_cols:
                    self._utype_to_cols[utype].add(col)
                else:
                    self._utype_to_cols[utype] = set((col,))

        if self.chunk_index:
            # Make sure all columns in the chunk index are known and
            # are type compatible.
            for c, t in izip(self.chunk_index.columns, self.chunk_index.types):
                if not c in self._dbname_to_col:
                    continue
                    #raise RuntimeError(str.format(
                    #    'chunk index file {0} references unknown column {1}.{2}',
                    #    self.chunk_index.path, self.id(), c))
                ct = self._dbname_to_col[c].type
                if not ct.compatible(formats.ASCII, t):
                    raise RuntimeError(str.format(
                        'chunk index column {0}:{1} is type-incompatible with {2}',
                        c, t, ct.get(formats.ADQL)))
            # Have UID and position columns, spatial searches supported
            self.uid = self._dbname_to_col[self.chunk_index.columns[0]]
            self.pos = (self._dbname_to_col[self.chunk_index.columns[1]],
                        self._dbname_to_col[self.chunk_index.columns[2]])
            # make columns not in chunk index unselectable
            for k, v in self._dbname_to_col.iteritems():
                if k not in self.chunk_index:
                    v.selectable = False
        else:
            # No spatial search allowed
            self.uid = None
            self.pos = None

        # Read in unique constraints
        self.unique = []
        for child in element.iterchildren(tag='unique'):
            refs = child.get('refs')
            if refs is None:
                raise RuntimeError(str.format(
                    'unique constraint on table {0} missing refs attribute',
                    self.id()))
            refs = refs.split(' ')
            constraint = set()
            for r in refs:
                if not r in self._name_to_col:
                    raise RuntimeError(str.format(
                        'unique constraint on table {0} references unknown column {1}',
                        self.id(), r))
                constraint.add(r)
            self.unique.append(constraint)

        # Read in image-set column identifiers
        self.image_set = set()
        elt = element.find('image_set')
        if elt is not None:
            refs = elt.get('refs')
            if refs is None:
                raise RuntimeError(str.format(
                    'image_set for table {0} missing refs attribute', self.id()))
            refs = refs.split(' ')
            for r in refs:
                if not r in self._name_to_col:
                    raise RuntimeError(str.format(
                        'image_set on table {0} references unknown column {1}',
                        self.id(), r))
                self.image_set.add(r)

        # Read in references to other tables
        self._refs_to = {}
        for child in element.iterchildren(tag='reference'):
            c = child.get('from')
            if not c in self._name_to_col:
                raise RuntimeError(str.format(
                    'reference in table {0} references unknown column {1}',
                    self.id(), c))
            dest = child.get('to')
            i = dest.rfind('.')
            if i <= 0 or i == len(dest) - 1:
                raise RuntimeError(str.format(
                    'reference in table {0} has invalid to attribute ({1})',
                    self.id(), dest))
            t = dest[:i]
            to = dest[i+1:]
            if t in self._refs_to:
                self._refs_to[t].append((c, to))
            else:
                self._refs_to[t] = [(c, to)]

        # Reflect database table
        self._sa_table = self.engine.table(self.dbname)
        for n in self._dbname_to_col:
            if not n in self._sa_table.c:
                raise RuntimeError(str.format('Table column {0}.{1} ' +
                    'mapped to database column {2} does not exist in ' +
                    'database table', self.id(), self._dbname_to_col[n].name, n))
            # Make sure all columns in the chunk index are known and
            # are type compatible.
            c = self._dbname_to_col[n]
            sa_c = self._sa_table.c[n]
            if not c.type.compatible(formats.SQLALCHEMY, sa_c.type):
                raise RuntimeError(str.format(
                    'logical column {0}:{1} is type-incompatible with {2}',
                    c.name, c.type.get(formats.ADQL), str(sa_c.type)))
            # store a reference to the sqlalchemy Column
            c._sa_column = sa_c
            c.nullable = sa_c.nullable
            c.indexed = any(n in i.columns for i in self._sa_table.indexes)

        # Deal with corner and WCS related columns
        elt = element.find('corners')
        if elt is not None:
            # This is an image metadata table -
            self.corners = Corners(elt, self)
            # Set up the ability to make WCSes from image table rows.
            self.wcsutils = WcsUtils(self)
            elt = element.find('center')
            self.center = Center(elt, self)
        else:
            self.corners = None
            self.center = None
            self.wcsutils = None

        # Read in location information for products
        elt = element.find('products')
        self.products = Products(elt) if elt is not None else None
        # Get SIA writer class
        elt = element.find('sia')
        if elt is None:
            self.sia_writer_class = None
        else:
            sia_writer_class = elt.get('writer')
            components = sia_writer_class.split('.')
            class_name = components.pop()
            if len(components) == 0:
                raise RuntimeError(str.format('SIA writer class name {0} ' +
                    'for table {1} not fully qualified', sia_writer_class,
                    self.id()))
            try:
                module_name = '.'.join(components)
                __import__(module_name)
                self.sia_writer_class = sys.modules[module_name].__dict__[class_name]
            except Exception, e:
                raise RuntimeError(str.format('Failed to lookup SIA writer ' +
                    'class {0} for table {1}',  sia_writer_class, self.id()))

    def id(self):
        return self.schema.id() + '.' + self.name

    def table(self):
        return self._sa_table

    def __getitem__(self, key):
        """Retrieves the column with the specified logical name.
        """
        if isinstance(key, Column):
            return self._name_to_col[key.name]
        else:
            return self._name_to_col[key]

    def __contains__(self, key):
        """Tests whether or not a column with the specified logical name exists.
        """
        if isinstance(key, Column):
            return key.name in self._name_to_col
        else:
            return key in self._name_to_col

    def __iter__(self):
        """Returns an iterator over the columns in this table.
        """
        return self._cols.__iter__()

    def __len__(self):
        """Returns the number of columns in this table.
        """
        return len(self._cols)

    tags = set(['nullable', 'selectable', 'queryable',
                'principal', 'indexed', 'std', 'constant'])

    def refs_to(self, table):
        """Returns a list of tuples ``(from, to)``, where ``from`` is the
        logical column name in this table corresponding to the logical column
        name ``to`` in ``table``. If there are no such references, ``None``
        is returned.
        """
        if isinstance(table, Table):
            tid = table.id()
        elif isinstance(table, basestring):
            tid = table
        else:
            raise TypeError("Expecting a Table or a table id string")
        return self._refs_to.get(tid, None)

    def iter(self, tag=None):
        """Returns an iterator over columns. An optional iteration tag
        (which must be one of the values in Table.tags) can be supplied to
        iterate only over specific (e.g. selectable) columns.
        """
        if tag is None:
            return self._cols.__iter__()
        elif tag in Table.tags:
            return (c for c in self._cols if c.__getattribute__(tag))
        raise RuntimeError(repr(tag) + ' is not a valid column iteration tag')

    def find(self, ucd, utype):
        """Returns the set of columns having the specified UCDs and UTYPEs.
        The parameters can be None, strings or iterables over strings, and
        at least one of the parameters must not be None. None parameters are
        wildcards, i.e. ucd=None will match a column regardless of its
        UCDs.
        """
        if ucd is None and utype is None:
            raise RuntimeError('No UCDs or UTYPEs provided for search')
        cset = None
        if ucd is not None:
            if isinstance(ucd, basestring):
                cset = set(self._ucd_to_cols[ucd]) if ucd in self._ucd_to_cols else set()
            else:
                for u in ucd:
                    s = set(self._ucd_to_cols[u]) if u in self._ucd_to_cols else set()
                    cset = cset & s if cset else s
        if utype is not None:
            if isinstance(utype, basestring):
                s = set(self._utype_to_cols[utype]) if utype in self._utype_to_cols else set()
                cset = cset & s if cset else s
            else:
                for u in utype:
                    s = set(self._utype_to_cols[u]) if u in self._utype_to_cols else set()
                    cset = cset & s if cset else s
        return cset

    def compute_row(self, row, wcs=None):
        computed_row = None
        corners = None
        center = None
        if self.corners and self.corners.computed:
            wcs = wcs or self.wcsutils.makeWcs(row)
            corners = self.wcsutils.corners(row, wcs)
            computed_row = dict()
            for i in xrange(8):
                computed_row[self.corners._columns[i].dbname] = corners[i >> 1, i & 1]
        if self.center and self.center.computed:
            wcs = wcs or self.wcsutils.makeWcs(row)
            center = self.wcsutils.center(row, wcs)
            computed_row = computed_row or dict()
            computed_row[self.center.columns[0].dbname] = center[0]
            computed_row[self.center.columns[1].dbname] = center[1]
        return computed_row


class Schema(collections.Mapping):
    """A collection of tables. This is conceptually the same as a database
    on an RDBMS server, but is a logical grouping only. The tables in a
    schema can live in different databases/servers on the back-end.

    A new table can be added to the collection, but any existing
    element is immutable. The collection is represented as a mapping of
    logical table names to Table objects.
    """
    def __init__(self, element, schema_group, engines):
        self._tables = {}
        self.schema_group = schema_group
        self.name = element.get('name')
        if self.name is None:
            raise RuntimeError('schema must have a name attribute')
        engine = element.get('engine')
        if engine is not None:
            if engine not in engines:
                raise KeyError('"{0}" is not a valid engine ID'.format(engine))
            engine = engines[engine]
        self.engine = engine
        desc = element.find('description')
        self.description = desc.text if desc is not None else None
        for child in element.iterchildren(tag='table'):
            name = child.get('name')
            if name in self._tables:
                raise RuntimeError('Duplicate definition for table {0}.{1}'.format(self.id(), name))
            self._tables[name] = Table(child, self, engines)

    def id(self):
        return self.schema_group.id() + '.' + self.name

    def __getitem__(self, key):
        """Retrieves the table with the specified logical name.
        """
        if isinstance(key, Table):
            return self._tables[key.name]
        else:
            return self._tables[key]

    def __contains__(self, key):
        """Tests whether or not a table with the specified logical name exists.
        """
        if isinstance(key, Table):
            return key.name in self._tables
        else:
            return key in self._tables

    def __iter__(self):
        """Returns an iterator over the logical names of the available tables.
        """
        return self._tables.__iter__()

    def __len__(self):
        """Returns the number of available tables.
        """
        return len(self._tables)

    def add(self, table):
        """Adds the given Table to this Schema.
        """
        if not isinstance(table, Table):
            raise TypeError('Expecting a Table')
        if table.name in self._tables:
            raise RuntimeError(str.format('schema {0} already contains table {1}',
                self.id(), table.id()))
        self._tables[table.name] = table
        table.schema = self


class SchemaGroup(collections.Mapping):
    """A collection of schemas; this is conceptually the same as a collection
    of databases living on an RDBMS server. For the moment, schema groups
    cannot be nested, and the group is not required to map to a collection
    of databases on a single RDBMS server.

    A new schema or table can be added, but any existing element is immutable.
    The collection is represented as a mapping of logical schema names to
    Schema objects.
    """
    def __init__(self, element, engines):
        self._schemas = {}
        self._id = element.get('id')
        if self._id is None:
            raise RuntimeError('schema_group must have an id attribute')
        for child in element.iterchildren(tag='schema'):
            name = child.get('name')
            if name in self._schemas:
                raise RuntimeError(
                    'Duplicate definition for schema {0}'.format(name))
            self._schemas[name] = Schema(child, self, engines)

    def id(self):
        return self._id

    def __getitem__(self, key):
        """Retrieves the element with the specified name. The name may refer to a
        schema, table or column, and must be of the form "schema[.table[.column]]".
        """
        if isinstance(key, basestring):
            i = key.find('.')
            if i == -1:
                return self._schemas[key]
            else:
                return self._schemas[key[:i]][key[i+1:]]
        raise KeyError('{0!r} is not a valid schema or table name'.format(key))

    def __contains__(self, key):
        """Tests whether or not an element with the specified name exists.
        The name may refer to a schema, table or column, and must be of the
        form "schema[.table[.column]]".

        For example, a key of "pass1.i1bm_frm" refers to the "i1bm_frm"
        table in the "pass1" schema.
        """
        if isinstance(key, basestring):
            i = key.find('.')
            if i == -1:
                return key in self._schemas
            else:
                k = key[:i]
                if k in self._schemas:
                    return key[i+1:] in self._schemas[k]
        return False

    def __iter__(self):
        """Returns an iterator over the names of the available schemas.
        """
        return self._schemas.__iter__()

    def __len__(self):
        """Returns the number of available schemas.
        """
        return len(self._schemas)

    def add(self, schema):
        """Adds the given Schema to this SchemaGroup.
        """
        if not isinstance(schema, Schema):
            raise TypeError('Expecting a Schema')
        if not schema.name in self._schemas:
            self._schemas[schema.name] = schema
            schema.schema_group = self
        else:
            s = self._schemas[schema.name]
            for tn in schema:
                s.add(schema[tn])


class Catalogs(collections.Mapping):
    """A collection of SchemaGroup objects. The collection is represented
    as a mapping of IDs to SchemaGroup objects. A new table, schema or
    schema group can be added to the collection, but existing elements
    in the hierarchy are immutable.
    """
    def __init__(self):
        self._schema_groups = {}

    def __getitem__(self, key):
        """Retrieves the element with the specified ID. The ID may refer
        to a schema group, schema or table, and must be of the form
        "schema_group[.schema[.table]]".
        """
        if isinstance(key, basestring):
            i = key.find('.')
            if i == -1:
                return self._schema_groups[key]
            else:
                return self._schema_groups[key[:i]][key[i+1:]]
        elif isinstance(key, (SchemaGroup, Schema, Table)):
            return self.__getitem__(key.id())
        raise KeyError('{0!r} is not a valid schema group, schema or table object or ID'.format(key))

    def __contains__(self, key):
        """Tests whether or not an element with the specified ID exists.
        The ID may refer to a schema group, schema or table, and
        must be of the form "schema_group[.schema[.table]]".

        For example, a key of "wise.pass1.i1bm_frm" refers to the "i1bm_frm"
        table in the "pass1" schema of the "wise" schema group.
        """
        if isinstance(key, basestring):
            i = key.find('.')
            if i == -1:
                return key in self._schema_groups
            else:
                k = key[:i]
                if k in self._schema_groups:
                    return key[i+1:] in self._schema_groups[k]
        elif isinstance(key, (SchemaGroup, Schema, Table)):
            return self.__contains__(key.id())
        return False

    def __iter__(self):
        """Returns an iterator over the IDs of the available schema groups.
        """
        return self._schema_groups.__iter__()

    def __len__(self):
        """Returns the number of available schema groups.
        """
        return len(self._schema_groups)

    def add(self, schema_group):
        """Adds the given SchemaGroup.
        """
        if not isinstance(schema_group, SchemaGroup):
            raise TypeError('Expecting a SchemaGroup')
        if not schema_group._id in self._schema_groups:
            self._schema_groups[schema_group._id] = schema_group
        else:
            sg = self._schema_groups[schema_group._id]
            for sn in schema_group:
                sg.add(schema_group[sn])

    def connectRoutes(self, mapper):
        mapper.connect('/search', controller='list', action='schema_groups')
        mapper.connect('/search/{schema_group}', controller='list', action='schemas')
        mapper.connect('/search/{schema_group}/', controller='list', action='schemas')
        mapper.connect('/search/{schema_group}/{schema}', controller='list', action='tables')
        mapper.connect('/search/{schema_group}/{schema}/', controller='list', action='tables')
        mapper.connect('/search/{schema_group}/{schema}/{table}',
                       controller='search', action='search')
        mapper.connect('/sia/{schema_group}/{schema}/{table}',
                       controller='search', action='sia')


def readCatalogs(catalogs_file, catalogs_schema, engines, catalogs=None):
    """Reads a configuration file describing a set of catalogs. Returns
    a Catalogs object containing configuration data

    - catalogs_file:   Path or file-like object for the XML configuration file.
    - catalogs_schema: Path or file-like object for the XML configuration file
                       schema.
    - engines:         A dictionary mapping database engine IDs (strings) to
                       Engine objects.
    - catalogs:        An optional Catalogs object to which the catalogs
                       from the configuration file should be added.
    """
    if not isinstance(engines, dict):
        raise TypeError('engines: expecting a dict, got a {0}.{1}'.format(
                        type(engines).__module__, type(engines).__name__))
    catalogs = catalogs or Catalogs()
    if not isinstance(catalogs, Catalogs):
        raise TypeError('catalogs: expecting a {0}.{1}, got a {2}.{3}'.format(
                        Catalogs.__module__, Catalogs.__name__,
                        type(catalogs).__module__, type(catalogs).__name__))
    # Read schema, read and validate configuration file
    xml_schema_doc = etree.parse(catalogs_schema)
    xml_schema = etree.XMLSchema(xml_schema_doc)
    doc = etree.parse(catalogs_file)
    xml_schema.assertValid(doc)
    # Build catalog configuration
    for element in doc.getroot().iterchildren(tag='schema_group'):
        schema_group = SchemaGroup(element, engines)
        catalogs.add(schema_group)
    return catalogs

