import csv
import os
import re
import string

# Enum of supported formats. Values must form a contiguous range
# of integers from 0 to NUM_FORMATS - 1.
ADQL = 0
SQLALCHEMY = 1
ASCII = 2
FITS = 3
VOTABLE = 4
NUM_FORMATS = 5


class IpacAsciiWriter(object):
    """Simple class for streaming output in IPAC ASCII table format.
    """
    def __init__(self, out, table, columns, server=None, url_root=None):
        self.out = out
        self.columns = []
        for c in columns:
            hw = max(map(len, (c.name, c.type.get(ASCII), c.unit or '', c.type.to_ascii(None) or '')))
            self.columns.append((max(hw, c.type.ascii_width()), c))
        # header:
        # 1. write out column names
        for w, c in self.columns:
            self.out.write('|')
            n = w - len(c.name)
            if n > 0:
                self.out.write(' ' * n)
            self.out.write(c.name)
        self.out.write('|\n')
        # 2. write out column types
        for w, c in self.columns:
            self.out.write('|')
            ascii_type = c.type.get(ASCII)
            n = w - len(ascii_type)
            if n > 0:
                self.out.write(' ' * n)
            self.out.write(ascii_type)
        self.out.write('|\n')
        # 3. write out column units
        for w, c in self.columns:
            self.out.write('|')
            unit = c.unit or ''
            n = w - len(unit)
            if n > 0:
                self.out.write(' ' * n)
            self.out.write(unit)
        self.out.write('|\n')
        # 4. write out column null values
        for w, c in self.columns:
            self.out.write('|')
            null_value = c.type.to_ascii(None) or ''
            n = w - len(null_value)
            if n > 0:
                self.out.write(' ' * n)
            self.out.write(null_value)
        self.out.write('|\n')

    def write(self, row, computed_row):
        o = self.out
        for w, c in self.columns:
            o.write(' ')
            if c.constant:
                v = c.type.to_ascii(c.const_val)
            elif c.computed:
                v = c.type.to_ascii(computed_row[c.dbname])
            else:
                v = c.type.to_ascii(row[c.dbname])
            n = w - len(v)
            if n > 0:
                o.write(' ' * n)
            o.write(v)
        o.write(' \n')

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    @staticmethod
    def content_type():
        return 'text/plain; charset=US-ASCII'


class DelimitedWriterBase(object):
    """Base class for writing out various dialects of character delimited tables.
    """
    def __init__(self, writer, table, columns):
        self.writer = writer
        self.columns = columns
        writer.writerow([c.name for c in columns])
        writer.writerow([c.type.get(ASCII) for c in columns])
        writer.writerow([c.unit or '' for c in columns])
        writer.writerow([c.type.to_ascii(None) or '' for c in columns])

    def write(self, row, computed_row):
        r = []
        for c in self.columns:
            if c.constant:
                r.append(c.type.to_ascii(c.const_val))
            elif c.computed:
                r.append(c.type.to_ascii(computed_row[c.dbname]))
            else:
                r.append(c.type.to_ascii(row[c.dbname]))
        self.writer.writerow(r)

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    @staticmethod
    def content_type():
        return 'text/plain; charset=UTF-8'


class CsvWriter(DelimitedWriterBase):
    """Comma separated value table writer.
    """
    def __init__(self, out, table, columns, server=None, url_root=None):
        writer = csv.writer(out,
                            quoting=csv.QUOTE_MINIMAL,
                            lineterminator='\r\n',
                            doublequote=True,
                            delimiter=',',
                            quotechar='"')
        super(CsvWriter, self).__init__(writer, table, columns)


class TsvWriter(DelimitedWriterBase):
    """Tab separated value table writer.
    """
    def __init__(self, out, table, columns, server=None, url_root=None):
        writer = csv.writer(out,
                            quoting=csv.QUOTE_MINIMAL,
                            lineterminator='\r\n',
                            doublequote=True,
                            delimiter='\t',
                            quotechar='"')
        super(TsvWriter, self).__init__(writer, table, columns)


class HtmlWriter(object):
    """Writer for producing HTML tables.
    """
    def __init__(self, out, table, columns, server=None, url_root=None):
        self.out = out
        # Output HTML header, open body, open table
        out.write("""\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
\t<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
\t<title>Results</title>
\t<style type="text/css">
\tbody {
\t\tfont-family: Helvetica, Arial, sans-serif;
\t\tfont-size: small;
\t\tcolor: black;
\t\tbackground-color: white;
\t}
\ttable {
\t\tborder-collapse:separate;
\t\tborder-spacing: 0.2em;
\t\tmargin: 1em 1em 1em 4em;
\t\twhite-space: nowrap;
\t}
\ttd {
\t\tmargin: 0.25em;
\t\tpadding: 0 0.5em 0 0.5em;
\t\ttext-align: left;
\t\tvertical-align: middle;
\t\tborder: 1px solid white;
\t}
\ttd.num {
\t\ttext-align: right;
\t}
\tth {
\t\tmargin: 0.25em;
\t\tpadding: 0.25em 0.5em 0.25em 0.5em;
\t\tfont-weight: bold;
\t\tcolor: grey;
\t\tbackground-color: #DDD;
\t\ttext-align: center;
\t\tvertical-align: middle;
\t\tborder: 1px solid white;
\t}
\tth.meta {
\t\tcolor: black;
\t\tbackground-color: #AAA;
\t}
\ttr:hover {
\t\tcolor: #00F;
\t\tbackground: #EEF;
\t\tborder: 1px solid blue;
\t}
\ttd:hover {
\t\tborder: 1px solid #DDF;
\t}
\t</style>
</head>
<body>
<div><table>""")
        # Output table header
        out.write('\n\t<tr><th class="meta">Column:</th><th>')
        out.write('</th><th>'.join([c.name for c in columns]))
        out.write('</th></tr>\n\t<tr><th class="meta">Type<th>')
        out.write('</th><th>'.join([c.type.get(ASCII) for c in columns]))
        out.write('</th></tr>\n\t<tr><th class="meta">Units<th>')
        out.write('</th><th>'.join([c.unit or '' for c in columns]))
        out.write('</th></tr>')
        css = []
        for c in columns:
            if c.type.get(ASCII) == 'char':
                css.append('')
            else:
                css.append(' class="num"')
        self.columns = zip(columns, css)

    def write(self, row, computed_row):
        o = self.out
        o.write('\n\t<tr><td>')
        for c, css in self.columns:
            o.write('</td><td')
            o.write(css)
            o.write('>')
            if c.constant:
                o.write(c.type.to_ascii(c.const_val, ''))
            elif c.computed:
                o.write(c.type.to_ascii(computed_row[c.dbname], ''))
            else:
                o.write(c.type.to_ascii(row[c.dbname], ''))
        o.write('</td></tr>')

    def close(self):
        # Close table and HTML body
        self.out.write('\n</table></div>\n</body>\n')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    @staticmethod
    def content_type():
        return 'text/html; charset=UTF-8'

