import os
import re
import string

from itertools import imap

__all__ = [ 'Column', 'Row', 'Reader' ]

def _identity(x): return x

class Column(object):
    """Meta-data container for a column in an IPAC ASCII table.
    """
    # Note: order is important!
    _types = [("char", _identity),
              ("double", float),
              ("date", _identity),
              ("datetime", _identity),
              ("float", float),
              ("long", long),
              ("integer", int),
              ("real", float),
             ]

    def __init__(self, name, datatype, units, null, ordinal, begin, end, typeCnv=True):
        def _check(x, property, required=False):
            if (not x or len(x.strip()) == 0) and required:
                raise ValueError("Column must have a " + property)
            if x and not isinstance(x, basestring):
                raise TypeError("Column " + property + " must be specified as a string")
        _check(name, "name", True)
        _check(datatype, "data type")
        _check(units, "unit specification")
        _check(null, "null specification")
        if not all(map(lambda x: isinstance(x, int), [ordinal, begin, end])):
            raise TypeError("Column ordinals and start/end character indexes must be integers")
        self.name = name.strip()
        self.units = units.strip() if units is not None else None
        self.null = null.strip() if null is not None else None
        self.ordinal = ordinal
        self.begin = begin
        self.end = end
        self.typeCnv = typeCnv
        self.set_type(datatype)

    def __str__(self):
        """Return a human readable description of the column.
        """
        return str.format(
           'Column {0}: "{1}", characters [{2}:{3})\n\ttype:  {4}\n\tunits: {5}\n\tnull:  {6}',
           self.ordinal, self.name, self.begin, self.end, self.type, self.units, self.null)

    def __len__(self):
        """Return the number of ASCII characters in a column value.
        """
        return self.end - self.begin

    def get(self, line, typeCnv=True):
        """Get the value of a field from a line of text. Convert nulls to
        None and map strings to a Python type based on the column data-type.
        """
        if self.begin > len(line):
            return None
        v = line[self.begin:min(self.end, len(line))].strip()
        if len(v) == 0:
            return None
        if self.null and v == self.null:
            return None
        return self.value(v) if typeCnv and self.typeCnv else v

    def set_type(self, datatype):
        """Set the type of the column.
        """
        if datatype is not None and len(datatype.strip()) > 0:
            datatype = datatype.strip()
            for t in Column._types:
                if t[0].startswith(datatype):
                    self.type, self.value = t[0], t[1]
                    return
            raise TypeError(str.format(
                'Unsupported data-type ({0}) for column {1}: "{2}"', datatype, self.ordinal, self.name))
        else:
            self.type = None
            self.value = _identity


class Row(tuple):
    """Simple tuple subclass that allows fields to be accessed by name
    as well as integer index.
    """
    def __new__(cls, iterable, index, columns, rowid):
        t = super(Row, cls).__new__(cls, iterable)
        t.index = index
        t.columns = columns
        t.rowid = rowid
        return t

    def __getitem__(self, key):
        if self.columns and isinstance(key, basestring):
            return tuple.__getitem__(self, self.index[key])
        return tuple.__getitem__(self, key)

    def dict(self):
        """Return a copy of this row as a column name to value map (dict).
        """
        data = dict((c.name, tuple.__getitem__(self, i)) for i, c in enumerate(self.columns))
        if 'rowid' not in data:
            data['rowid'] = self.rowid
        return data

    def keys(self):
        """Return a copy of the column names for the fields in this row (in field order).
        """
        return [c.name for c in self.columns]

    def iterkeys(self):
        """Return an iterator over the column names for the fields in this row.
        Names are produced in field order.
        """
        return (c.name for c in self.columns)

    def items(self):
        """Return a list of column name, field value tuples for the row (in field order).
        """ 
        return [(c.name, tuple.__getitem__(self, i)) for i, c in enumerate(self.columns)]

    def iteritems(self):
        """Return an iterator over column name, field value tuples for the row. Tuples
        are produced in field order.
        """
        return ((c.name, tuple.__getitem__(self, i)) for i, c in enumerate(self.columns))


class Reader(object):
    """Class for reading fixed-length IPAC ASCII tables.
    """
    def __init__(self, tableFile, firstRow=0, typeCnv=True):
        """Open an IPAC ASCII table file for reading. The iterator protocol is supported and
        the starting row can be specified using the `firstRow` constructor parameter. Negative
        row numbers are interpreted relative to the end of the table (-1 is the last row), and
        values that are out of range are clamped to the beginning or end of the table (row -200
        in a 100 row table is equivalent to row 0). The `typeCnv` constructor argument determines
        whether automatic string to Python type conversions take place; if set to False, then
        the original column contents are preserved and presented as strings regardless of the
        specified column type.
        """
        if isinstance(tableFile, basestring):
            self._path = tableFile
            self._file = open(tableFile, 'rb')
        else:
            try:
                self._path = tableFile.name
            except AttributeError:
                self._path = ''
            self._file = tableFile
        self._comments = []
        hdr = []
        self._dataOffset = 0

        line = self._file.readline()
        # read comments
        while line.startswith('\\'):
            self._comments.append(line)
            line = self._file.readline()
        # read header lines
        while line.startswith('|'):
            self._dataOffset = self._file.tell()
            hdr.append(line)
            line = self._file.readline()

        self._lineLength = self._file.tell() - self._dataOffset

        if len(hdr) < 1 or len(hdr) > 4:
            raise RuntimeError("IPAC ASCII file " + self._path +
                               " must have between 1 and 4 header lines")

        # find the index of | characters in all header lines
        pipes = [[m.start() for m in re.finditer(r'\|', l)] for l in hdr]
        p0 = pipes[0]
        if len(p0) < 2:
            raise RuntimeError("header line in IPAC ASCII file " + self._path +
                               " is missing column delimiter")
        if hdr[0][-2] != '|':
            raise RuntimeError("header line in IPAC ASCII file " + self._path +
                               " is not terminated by '|'")
        if not all(len(hdr[0]) == len(l) for l in hdr[1:]):
            raise RuntimeError("header lines in IPAC ASCII file " + self._path +
                               " must all have the same length")
        if not all(p0 == p for p in pipes[1:]):
            raise RuntimeError("Column separators in header lines of IPAC ASCII file " +
                               self._path + " are not vertically aligned")
        ncol = len(p0) - 1

        # given a string and a list of delimiter locations, return whitespace stripped tokens
        _tostrip = string.whitespace + '-'
        def _tok(line, idx):
            return [line[s[0]+1:s[1]].strip(_tostrip) for s in imap(lambda i: idx[i:i+2], xrange(ncol))]

        # extract column attributes from header lines
        n, t, u, N = [_tok(hdr[i], p0) if len(hdr) > i else [None]*ncol for i in xrange(4)]
        # Create column meta-data
        self._index = dict((n[i], i) for i in xrange(ncol))
        self._columns = [Column(n[i], t[i], u[i], N[i], i, p0[i], p0[i+1], typeCnv) for i in xrange(ncol)]
        # Compute total number of records in file, seek to first row
        if self._lineLength == 0:
            self._numRows = 0
            self._rowid = 0
        else:
            self._file.seek(0, os.SEEK_END)
            end = self._file.tell()
            quo = (end - self._dataOffset) / self._lineLength
            rem = (end - self._dataOffset) % self._lineLength
            # allow truncation of the last line
            self._numRows = quo if rem == 0 else quo + 1
            self._rowid = firstRow
            self.seek(firstRow)

    def path(self):
        """Return the pathname of the table file (may be None,
        e.g. when reading unnamed temporary files).
        """
        return self._path

    def columns(self):
        """Return a list of the columns in the table.
        """
        return self._columns

    def column(self, name):
        """Return the column with the given name.
        """
        return self._columns[self._index[name]]

    def comments(self):
        """Return a list of the comment lines in the table file header.
        """
        return self._comments

    def __iter__(self):
        """Return self; IPAC ASCII table file readers are also iterators.
        """
        return self

    def __contains__(self, column):
        """Test if a column with the specified name or index exists in the table.
        """
        if isinstance(column, int):
            return column >= 0 and column < len(self._columns)
        return column in self._index

    def next(self):
        """Return the next row in the table, or raise StopIteration
        if the last row has been returned.
        """
        if self._file is None:
            raise RuntimeError('IPAC ASCII table file has already been closed')
        line = self._file.readline()
        if len(line) == 0:
            raise StopIteration()
        self._rowid += 1
        if self._rowid != self._numRows and len(line) != self._lineLength:
            raise RuntimeError("IPAC ASCII table row does not have the expected length")
        return Row([c.get(line) for c in self._columns],
                   self._index, self._columns, self._rowid - 1)

    def seek(self, row):
        """Seek to the specified row number (0-based). A negative row number is
        interpreted relative to the end of the table, e.g. -1 corresponds to the
        last row of the table. Row numbers that fall out of range are clamped
        to the beginning or end of the table.
        """
        if self._file is None:
            raise RuntimeError('IPAC ASCII table file has already been closed')
        if isinstance(row, Row):
            row = row.rowid
        if row < -self._numRows: row = -self._numRows
        if row > self._numRows: row = self._numRows
        if row < 0: row += self._numRows
        self._rowid = row
        self._file.seek(self._dataOffset + row * self._lineLength)

    def numRows(self):
        """Return the total number of records in the table.
        """
        return self._numRows

    def rowid(self):
        """Return the current row number.
        """
        return self._rowid

    def close(self):
        """Closes the underlying table file.
        """
        if self._file is not None:
            self._file.close()
            self._file = None
            self._rowid = None

