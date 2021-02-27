import abc
import base64
import datetime
import decimal
import formats
import re
import sqlalchemy as sa

# -- Abstract base classes for column data types ----

class ColumnType(object):
    """Abstract base class for column types.
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def ascii_width(self):
        """Returns the maximum size in bytes of a single value of the
        specified type when converted to ASCII.
        """
        return

    @abc.abstractmethod
    def to_ascii(self, value, null_value=None):
        """Converts a value to an ASCII string, e.g. for output to an
        IPAC ASCII, CSV or TSV table.
        """
        return

    @abc.abstractmethod
    def to_python(self, ascii):
        """Converts an ASCII value to Python value.
        """
        return

    @abc.abstractmethod
    def get(self, format):
        """Returns a representation of the type of a value
        as understood by a specific output format.
        """
        return

    @abc.abstractmethod
    def compatible(self, format, spec):
        """Returns True if a type specification for a particular format
        is compatible with this ColumnType.
        """
        return


_fmt_re = re.compile(r'^(?:[^\}]?[<>=\^])?[+\- ]?#?0?([1-9]+[0-9]*)?(?:\.([1-9]+[0-9]*))?([bcdeEfFgGsxX]?)$')

class FormattableColumnType(ColumnType):
    """Base class for concrete column type implementations that support
    user specifiable string formatting specifications.
    """
    def __init__(self, width, def_fmt, fmt, null_value):
        if fmt:
            m = _fmt_re.match(fmt)
            if m is None:
                raise RuntimeError(fmt + ' is not a valid column formatting spec')
            if m.group(1):
                width = int(m.group(1))
        self._format_spec = '{{0:{0}}}'.format(fmt or def_fmt)
        self._ascii_width = width
        self._null_value = null_value

    def ascii_width(self):
        return self._ascii_width

    def to_ascii(self, value, null_value=None):
        if isinstance(value, basestring):
            value = self.to_python(value)
        if value is None:
            return null_value if null_value is not None else self._null_value
        return self._format_spec.format(value)

    def get(self, format):
        if format < 0 or format >= len(self._type_reprs):
            return None
        return self._type_reprs[format]

def _int_compatible(self, format, spec):
    if format == formats.ADQL:
        return spec in ('SMALLINT', 'INTEGER', 'BIGINT')
    elif format == formats.SQLALCHEMY:
        return isinstance(spec, (sa.types.Integer, sa.types.SmallInteger, sa.types.Numeric))
    elif format == formats.ASCII:
        return spec.strip().lower() in ('i', 'int', 'l', 'long')
    elif format == formats.FITS:
        return spec in ('I', 'J', 'K', '1I', '1J', '1K')
    elif format == formats.VOTABLE:
        return spec[1] in (None, '1') and spec[0] in ('short', 'int', 'long')
    raise RuntimeError('Unknown/unsupported format')

def _fp_compatible(self, format, spec):
    if format == formats.ADQL:
        return spec in ('REAL', 'DOUBLE') or spec.startswith('DECIMAL')
    elif format == formats.SQLALCHEMY:
        return isinstance(spec, (sa.types.Float, sa.types.Numeric))
    elif format == formats.ASCII:
        return spec.strip().lower() in ('f', 'float', 'r', 'real', 'd', 'double')
    elif format == formats.FITS:
        return spec in ('E', 'D', '1E', '1D')
    elif format == formats.VOTABLE:
        return spec[1] in (None, '1') and spec[0] in ('float', 'double')
    raise RuntimeError('Unknown/unsupported format')


# -- Value types ----
#
# Note that columns containing arrays of the primitive types
# are currently not supported. Support for the bit and boolean
# types of the FITS/VOTable standards is also currently missing.

class SmallInt(FormattableColumnType):
    """A 16 bit integer.
    """
    def __init__(self, format_spec, null_value):
        FormattableColumnType.__init__(self, 6, 'd', format_spec, null_value)

    _type_reprs = [ 'SMALLINT', sa.types.SmallInteger(),
                    'int', 'I', ('short', None) ]

    compatible = _int_compatible

    def to_python(self, ascii):
        if ascii == self._null_value:
            return None
        return int(ascii)


class Integer(FormattableColumnType):
    """A 32 bit integer.
    """
    def __init__(self, format_spec, null_value):
        FormattableColumnType.__init__(self, 10, 'd', format_spec, null_value)

    _type_reprs = [ 'INTEGER', sa.types.Integer(),
                    'int', 'J', ('int', None) ]

    compatible = _int_compatible

    def to_python(self, ascii):
        if ascii == self._null_value:
            return None
        return int(ascii)


class BigInt(FormattableColumnType):
    """A 64 bit integer.
    """
    def __init__(self, format_spec, null_value):
        FormattableColumnType.__init__(self, 20, 'd', format_spec, null_value)

    _type_reprs = [ 'BIGINT', sa.types.Integer(),
                    'long', 'K', ('long', None) ]

    compatible = _int_compatible

    def to_python(self, ascii):
        if ascii == self._null_value:
            return None
        return long(ascii)


class Real(FormattableColumnType):
    """A single precision floating point number.
    """
    def __init__(self, format_spec, null_value):
        FormattableColumnType.__init__(self, 15, '.9g', format_spec, null_value)

    _type_reprs = [ 'REAL', sa.types.Float(9),
                    'float', 'E', ('float', None) ]

    compatible = _fp_compatible

    def to_python(self, ascii):
        if ascii == self._null_value:
            return None
        return float(ascii)


class Double(FormattableColumnType):
    """A double precision floating point number.
    """
    def __init__(self, format_spec, null_value):
        FormattableColumnType.__init__(self, 24, '.17g', format_spec, null_value)

    _type_reprs = [ 'DOUBLE', sa.types.Float(17),
                    'double', 'D', ('double', None) ]

    compatible = _fp_compatible

    def to_python(self, ascii):
        if ascii == self._null_value:
            return None
        return float(ascii)


class Decimal(ColumnType):
    """A decimal number.
    """
    def __init__(self, precision, scale, null_value):
        if precision < 0 or scale < 0 or precision < scale:
            raise RuntimeError('Invalid decimal precision and/or scale')
        self.precision = precision
        self.scale = scale
        if scale > 0:
            self._format_spec = '{{0:{0}.{1}f}}'.format(precision + 2, scale)
            self._ascii_width = precision + 2
        else:
            self._format_spec = '{{0:{0}.0f}}'.format(precision + 1)
            self._ascii_width = precision + 1
        self._null_value = null_value

    def ascii_width(self):
        return self._ascii_width

    def to_ascii(self, value, null_value=None):
        if isinstance(value, basestring):
            value = self.to_python(value)
        if value is None:
            return null_value if null_value is not None else self._null_value
        return self._format_spec.format(value)

    def get(self, format):
        if format == formats.ADQL:
            return 'DECIMAL({0},{1})'.format(self.precision, self.scale)
        elif format == formats.SQLALCHEMY:
            #TODO: this is a hack!
            if self.scale == 0:
                return sa.types.Integer()
            return sa.types.Float(self.precision, asdecimal=False)
            #return sa.types.Decimal(self.precision, self.scale)
        elif format == formats.ASCII:
            if self.scale == 0:
                return 'long' if self.precision >= 9 else 'int'
            return 'double' if self.precision > 6 else 'float'
        elif format == formats.FITS:
            if self.scale == 0:
                return 'K' if self.precision >= 9 else 'J'
            return 'D' if self.precision > 6 else 'E'
        elif format == formats.VOTABLE:
            if self.scale == 0: 
                return ('long', None) if self.precision >= 9 else ('int', None)
            return ('double', None) if self.precision > 6 else ('float', None)
        else:
            raise RuntimeError('unsupported/unknown format')

    def compatible(self, format, spec):
        if self.scale == 0:
            return _int_compatible(self, format, spec)
        else:
            return _fp_compatible(self, format, spec)

    def to_python(self, ascii):
        if ascii == self._null_value:
            return None
        return decimal.Decimal(ascii)

class Date(ColumnType):
    """An idealized date.
    """
    def __init__(self, format_spec, null_value):
        self._format_spec = format_spec
        self._ascii_width = 10
        self._null_value = null_value

    def ascii_width(self):
        return self._ascii_width

    def to_ascii(self, value, null_value=None):
        if value is None:
            return null_value if null_value is not None else self._null_value
        return value.strftime(self._format_spec) if self._format_spec else value.isoformat()

    _type_reprs = [ 'DATE', sa.types.Date(), 'char', '10A', ('char', '10*') ]

    def get(self, format):
        if format < 0 or format >= len(self._type_reprs):
            return None
        return self._type_reprs[format]

    def compatible(self, format, spec):
        if format == formats.ADQL:
            return spec in ('DATE', 'CHAR', 'VARCHAR')
        elif format == formats.SQLALCHEMY:
            return isinstance(spec, (sa.types.DateTime, sa.types.Date, sa.types.String, sa.types.Unicode))
        elif format == formats.ASCII:
            return spec.strip().lower() in ('date', 'c', 'char')
        elif format == formats.FITS:
            return spec[-1] == 'A'
        elif format == formats.VOTABLE:
            return spec[0] == ('char') and re.matches('^[1-9]+[0-9]*\*?$', spec[1])
        raise RuntimeError('Unknown/unsupported format')

    def to_python(self, ascii):
        if ascii == self._null_value:
            return None
        dt = datetime.date.strptime(ascii, self._format_spec or '%Y-%m-%d')
        return datetime.date(dt.year, dt.month, dt.day)

class Time(ColumnType):
    """An idealized time.
    """
    def __init__(self, format_spec, null_value):
        self._format_spec = format_spec
        self._ascii_width = 10
        self._null_value = null_value

    def ascii_width(self):
        return self._ascii_width

    def to_ascii(self, value, null_value=None):
        if value is None:
            return null_value if null_value is not None else self._null_value
        return value.strftime(self._format_spec) if self._format_spec else value.isoformat()

    _type_reprs = [ 'TIME', sa.types.Time(), 'char', '15A', ('char', '15*') ]

    def get(self, format):
        if format < 0 or format >= len(self._type_reprs):
            return None
        return self._type_reprs[format]

    def compatible(self, format, spec):
        if format == formats.ADQL:
            return spec in ('TIME', 'CHAR', 'VARCHAR')
        elif format == formats.SQLALCHEMY:
            return isinstance(spec, (sa.types.DateTime, sa.types.Time, sa.types.String, sa.types.Unicode))
        elif format == formats.ASCII:
            return spec.strip().lower() in ('time', 'c', 'char')
        elif format == formats.FITS:
            return spec[-1] == 'A'
        elif format == formats.VOTABLE:
            return spec[0] == ('char') and re.matches('^[1-9]+[0-9]*\*?$', spec[1])
        raise RuntimeError('Unknown/unsupported format')

    def to_python(self, ascii):
        if ascii == self._null_value:
            return None
        if self._format_spec:
            dt = datetime.datetime.strptime(ascii, self._format_spec)
        else:
            dt = datetime.datetime.strptime(ascii, '%H:%M:%S.%f' if ascii.find('.') != -1 else '%H:%M:%S')
        return datetime.time(dt.hour, dt.minute, dt.second, dt.microsecond)

class DateTime(ColumnType):
    """A date and time.
    """
    def __init__(self, format_spec, null_value):
        self._format_spec = format_spec
        self._ascii_width = 26
        self._null_value = null_value

    def ascii_width(self):
        return self._ascii_width

    def to_ascii(self, value, null_value=None):
        if value is None:
            return null_value if null_value is not None else self._null_value
        return value.strftime(self._format_spec) if self._format_spec else value.isoformat(' ')

    _type_reprs = [ 'DATETIME', sa.types.DateTime(),
                    'char', '26A', ('char', '26*') ]

    def get(self, format):
        if format < 0 or format >= len(self._type_reprs):
            return None
        return self._type_reprs[format]

    def compatible(self, format, spec):
        if format == formats.ADQL:
            return spec in ('DATETIME', 'DATE', 'TIMESTAMP', 'CHAR', 'VARCHAR')
        elif format == formats.SQLALCHEMY:
            return isinstance(spec, (sa.types.DateTime, sa.types.Date, sa.types.String, sa.types.Unicode))
        elif format == formats.ASCII:
            return spec.strip().lower() in ('date', 'datetime', 'c', 'char')
        elif format == formats.FITS:
            return spec[-1] == 'A'
        elif format == formats.VOTABLE:
            return spec[0] == ('char') and re.matches('^[1-9]+[0-9]*\*?$', spec[1])
        raise RuntimeError('Unknown/unsupported format')

    def to_python(self, ascii):
        if ascii == self._null_value:
            return None
        if self._format_spec:
            return datetime.datetime.strptime(ascii, self._format_spec)
        if ascii.find('.') != -1:
            return datetime.datetime.strptime(ascii, '%Y-%m-%d %H:%M:%S.%f')
        return datetime.datetime.strptime(ascii, '%Y-%m-%d %H:%M:%S')

class Char(ColumnType):
    """An array of characters.
    """
    def __init__(self, size, null_value):
        if size < 0:
            raise RuntimeError('Invalid character string length')
        self.size = size
        self._null_value = null_value

    def ascii_width(self):
        return self.size

    def to_ascii(self, value, null_value=None):
        if value is None:
            return null_value if null_value is not None else self._null_value
        return '{0:s}'.format(value)

    def get(self, format):
        if format == formats.ADQL:
            return 'CHAR({0})'.format(self.size)
        elif format == formats.SQLALCHEMY:
            return sa.types.String(self.size)
        elif format == formats.ASCII:
            return 'char'
        elif format == formats.FITS:
            return '{0}A'.format(self.size)
        elif format == formats.VOTABLE:
            return 'char', str(self.size)
        else:
            return None

    def compatible(self, format, spec):
        if format == formats.ADQL:
            return spec in ('CHAR', 'VARCHAR')
        elif format == formats.SQLALCHEMY:
            return isinstance(spec, (sa.types.String, sa.types.Unicode))
        elif format == formats.ASCII:
            return spec.strip().lower() in ('c', 'char')
        elif format == formats.FITS:
            return spec[-1] == 'A'
        elif format == formats.VOTABLE:
            return spec[0] == ('char') and (spec[1] is None or re.matches('^[0-9]*\*?$', spec[1]))
        raise RuntimeError('Unknown/unsupported format')

    def to_python(self, ascii):
        if ascii == self._null_value:
            return None
        return ascii


class VarChar(Char):
    """A variable length array of characters.
    """
    def __init__(self, size, null_value):
        Char.__init__(self, size, null_value)

    def get(self, format):
        if format == formats.ADQL:
            return 'VARCHAR({0})'.format(self.size)
        elif format == formats.SQLALCHEMY:
            return sa.types.String(self.size)
        elif format == formats.ASCII:
            return 'char'
        elif format == formats.FITS:
            return 'AP({0})'.format(self.size)
        elif format == formats.VOTABLE:
            return 'char', '{0}*'.format(self.size)
        else:
            return None


class Binary(ColumnType):
    """An array of bytes.
    """
    def __init__(self, size, null_value):
        if size <= 0:
            raise RuntimeError('Invalid byte string length')
        self.size = size
        self._ascii_width = (size + 2 - ((size + 2) % 3)) / 3 * 4
        self._null_value = null_value

    def ascii_width(self):
        return self._ascii_width

    def to_ascii(self, value, null_value=None):
        if value is None:
            return null_value if null_value is not None else self._null_value
        return base64.standard_b64encode(value)

    def get(self, format):
        if format == formats.ADQL:
            return 'BINARY({0})'.format(self.size)
        elif format == formats.SQLALCHEMY:
            return sa.types.Binary(self.size)
        elif format == formats.ASCII:
            return 'char'
        elif format == formats.FITS:
            return '{0}B'.format(self.size)
        elif format == formats.VOTABLE:
            return 'unsignedByte', str(self.size)
        else:
            return None

    def compatible(self, format, spec):
        if format == formats.ADQL:
            return spec in ('BINARY', 'VARBINARY')
        elif format == formats.SQLALCHEMY:
            return isinstance(spec, sa.types.Binary)
        elif format == formats.ASCII:
            return spec.strip().lower() in ('c', 'char')
        elif format == formats.FITS:
            return spec[-1] == 'B'
        elif format == formats.VOTABLE:
            return spec[0] == ('unsignedByte') and (spec[1] is None or re.matches('^[0-9]*\*?$', spec[1]))
        raise RuntimeError('Unknown/unsupported format')

    def to_python(self, ascii):
        if ascii == self._null_value:
            return None
        return base64.standard_b64decode(ascii)


class VarBinary(Binary):
    """A variable length array of bytes.
    """
    def __init__(self, size, null_value):
        Binary.__init__(self, size, null_value)

    def get(self, format):
        if format == formats.ADQL:
            return 'VARBINARY({0})'.format(self.size)
        elif format == formats.SQLALCHEMY:
            return sa.types.Binary(self.size)
        elif format == formats.ASCII:
            return 'char'
        elif format == formats.FITS:
            return 'BP({0})'.format(self.size)
        elif format == formats.VOTABLE:
            return 'unsignedByte', '{0}*'.format(self.size)
        else:
            return None


# -- Type object creation from a format specific datatype specification ----

_var_re = re.compile(r'^((?:VAR)?(?:CHAR|BINARY))\s*\(\s*(\d+)\s*\)$')
_dec_re = re.compile(r'^DECIMAL\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)$')

def from_adql(datatype, format_spec, null_value):
    """Returns a ColumnType object for the given ADQL datatype string.
    """
    if not isinstance(datatype, basestring):
        raise TypeError('ADQL datatype must be a str/unicode object')
    if format_spec is not None and not isinstance(datatype, basestring):
        raise TypeError('Formatting spec must be None or a str/unicode object')
    if datatype == 'SMALLINT':
        return SmallInt(format_spec, null_value)
    elif datatype == 'INTEGER':
        return Integer(format_spec, null_value)
    elif datatype == 'BIGINT':
        return BigInt(format_spec, null_value)
    elif datatype == 'REAL':
        return Real(format_spec, null_value)
    elif datatype == 'DOUBLE':
        return Double(format_spec, null_value)
    elif datatype == 'DATE':
        return Date(format_spec, null_value)
    elif datatype == 'DATETIME':
        return DateTime(format_spec, null_value)
    elif datatype == 'TIME':
        return Time(format_spec, null_value)
    m = _dec_re.match(datatype)
    if m:
        if format_spec is not None:
            raise RuntimeError('DECIMAL column cannot have a format spec')
        return Decimal(int(m.group(1)), int(m.group(2)), null_value)
    m = _var_re.match(datatype)
    if m is None:
        raise RuntimeError(datatype + ' is not a valid ADQL datatype')
    t = m.group(1)
    s = int(m.group(2))
    if format_spec is not None:
        raise RuntimeError(t + ' column cannot have a format spec')
    if t == 'CHAR':
        return Char(s, null_value)
    elif t == 'VARCHAR':
        return VarChar(s, null_value)
    elif t == 'BINARY':
        return Binary(s, null_value)
    return VarBinary(s, null_value)


def from_ascii(datatype, width, format_spec, null_value):
    """Returns a ColumnType object for the given IPAC ASCII datatype string.
    """
    if not isinstance(datatype, basestring):
        raise TypeError('ASCII datatype must be a str/unicode object')
    if not isinstance(width, int):
        raise TypeError('Field width must be an int')
    if format_spec is not None and not isinstance(datatype, basestring):
        raise TypeError('Formatting spec must be None or a str/unicode object')
    dt = datatype.strip().lower()
    if dt in ('c', 'char'):
        if format_spec is not None:
            raise RuntimeError('char column cannot have a format spec')
        return Char(width, null_value)
    elif dt in ('i', 'int', 'integer'):
        return Integer(format_spec, null_value)
    elif dt in ('l', 'long'):
        return BigInt(format_spec, null_value)
    elif dt in ('r', 'real', 'f', 'float'):
        return Real(format_spec, null_value)
    elif dt in ('d', 'double'):
        return Double(format_spec, null_value)
    elif dt == 'date':
        return Date(null_value)
    elif dt == 'time':
        return Time(null_value)
    elif dt == 'datetime':
        return DateTime(null_value)


def from_fits(datatype, format_spec, null_value):
    raise NotImplementedError()


def from_votable(datatype, arraysize, format_spec, null_value):
    raise NotImplementedError()

