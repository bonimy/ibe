#! /usr/bin/env python
import collections
import contextlib
import cookielib
import csv
import datetime
import errno
import numpy
import optparse
import os
import pdb
import pyfits
import pywcs
import re
import shutil
import socket
import subprocess
import unittest
import urllib2


# -- Unit test data ----

GROUP_ALL = -99

User = collections.namedtuple('User', ['name', 'password', 'groups'])

# Users used by the access control tests.
users = [
    User('ibe_unittest_1@ipac.caltech.edu', 'password', set([1,3,5,7])),
    User('ibe_unittest_2@ipac.caltech.edu', 'password', set([2,4,6,8])),
    User('ibe_unittest_3@ipac.caltech.edu', 'password', set([1,2,3,4,5,6,7,8,9])),
    User('ibe_unittest_4@ipac.caltech.edu', 'password', set([10,11])),
    User('ibe_unittest_5@ipac.caltech.edu', 'password', set([GROUP_ALL])),
    User('anonymous', None, set()),
]

Record = collections.namedtuple('Record', ['id', 'gid', 'x', 'pubdate', 'path'])

_past = datetime.datetime(1800, 1, 1, 0, 0, 0)
_future = datetime.datetime(2200, 1, 1, 0, 0, 0)

# Content of the database table used by the access control tests.
records = [
    Record(1,  1,  5, _past,   '123/1/f1.fits'),
    Record(2,  1, -5, _future, '123/1/f2.fits'),
    Record(3,  2,  5, _past,   '123/2/f3.fits'),
    Record(4,  2, -5, _future, '123/2/f4.fits'),
    Record(5,  3,  5, _past,   '123/3/f5.fits'),
    Record(6,  3, -5, _future, '123/3/f6.fits'),
    Record(7,  4,  5, _past,   '45/4/f7.fits'),
    Record(8,  4, -5, _future, '45/4/f8.fits'),
    Record(9,  5,  5, _past,   '45/5/f9.fits'),
    Record(10, 5, -5, _future, '45/5/f10.fits'),
    Record(11, 6,  5, _past,   '6789/6/f11.fits'),
    Record(12, 6, -5, _future, '6789/6/f12.fits'),
    Record(13, 7,  5, _past,   '6789/7/f13.fits'),
    Record(14, 7, -5, _future, '6789/7/f14.fits'),
    Record(15, 8,  5, _past,   '6789/8/f15.fits'),
    Record(16, 8, -5, _future, '6789/8/f16.fits'),
    Record(17, 9,  5, _past,   '6789/9/f17.fits'),
    Record(18, 9, -5, _future, '6789/9/f18.fits'),
]

# Group ID of the table in the "ACCESS_TABLE" test.
table_group = 2


# -- Helper functions/objects ----

def get_expected_results(table, user, path=''):
    """Return list of all records that could be returned by an
    IBE search on the given table, optionally restricted to
    those with the given path prefix.
    """
    now = datetime.datetime.utcnow()
    if table == 'unittest/access/denied':
        return []
    elif table == 'unittest/access/granted':
        return [r for r in records if r.path.startswith(path)]
    elif table == 'unittest/access/table':
        if table_group in user.groups or GROUP_ALL in user.groups:
            return [r for r in records if r.path.startswith(path)]
        return []
    elif table == 'unittest/access/row_only':
        return [r for r in records if r.path.startswith(path) and (
            r.gid in user.groups or
            GROUP_ALL in user.groups)]
    elif table == 'unittest/access/date_only':
        return [r for r in records if r.path.startswith(path) and
            r.pubdate <= now]
    elif table == 'unittest/access/row_date':
        return [r for r in records if r.path.startswith(path) and (
            r.pubdate <= now or
            r.gid in user.groups or
            GROUP_ALL in user.groups)]

 
def check_output(*popenargs, **kwargs):
    """Equivalent to subprocess.check_output in Python 2.7;
    included here so that we can run with Python 2.6.
    """
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')
    process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
    output, unused_err = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = kwargs.get('args')
        if cmd is None:
            cmd = popenargs[0]
        raise subprocess.CalledProcessError(retcode, cmd, output=output)
    return output


# A dict mapping test user-names to URL openers. Each opener uses a cookie jar
# holding a user-specific session ID, ensuring that IBE responses are tailored
# to the corresponding test user.
url_openers = dict()

# Add a URL opener for every test user
for user in users:
    cookie_jar = cookielib.CookieJar()
    if user.name != 'anonymous':
        # Get session ID using ssologin
        ssologin = os.path.join(os.environ['CM_BASE_DIR'], 'bin', 'ssologin')
        ssoclientconf = os.path.join(os.path.dirname(__file__), 'unittest', 'ssoclient.conf')
        session_id = check_output([
            ssologin, '-f', ssoclientconf, '-u', user.name, '-p', user.password])
        # Construct cookie and add it to the jar
        cookie = cookielib.Cookie(
            version=None,
            name='JOSSO_SESSIONID',
            value=session_id,
            port=None,
            port_specified=False,
            domain='.ipac.caltech.edu',
            domain_specified=False,
            domain_initial_dot=True,
            path='/',
            path_specified=True,
            secure=None,
            expires=None,
            discard=None,
            comment=None,
            comment_url=None,
            rest=None)
        cookie_jar.set_cookie(cookie)
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookie_jar))
    url_openers[user.name] = opener


def ibe_run_search(ctx, user, url):
    """Runs an IBE search. Assumes the output format is CSV.
    """
    opener = url_openers[user.name]
    results = []
    f = None
    try:
        f = opener.open(url)
        # Get query results
        reader = csv.DictReader(
            f,
            quoting=csv.QUOTE_MINIMAL,
            lineterminator='\r\n',
            doublequote=True,
            delimiter=',',
            quotechar='"')
        # skip 3 rows: type names, units, and null specs
        for i in xrange(3):
            reader.next()
        for row in reader:
            results.append(row)
    except urllib2.HTTPError as h:
        if h.code not in (401, 403):
            ctx.fail('Failed to retrieve %s: %s' % (url, str(h)))
    finally:
        if f is not None:
            f.close()
    return results


def ibe_get_data(ctx, user, url):
    """Retrieves a file or directory listing from an IBE server.
    """
    opener = url_openers[user.name]
    f = None
    results = None
    try:
        f = opener.open(url)
        results = f.read()
    except urllib2.HTTPError as h:
        if h.code not in (401, 403, 404):
            ctx.fail('Failed to retrieve %s: %s' % (url, str(h)))
    finally:
        if f is not None:
            f.close()
    return results


def scrape_dir_contents(html):
    """Scrapes a directory listing from HTML with a simple regular
    expression. Assumes all relative links correspond to a directory entry.
    """
    if html is None:
        return None
    contents = set()
    for m in re.finditer('<a href="([^/].*)"', html):
        contents.add(m.group(1))
    return contents


def ensure_dir_exists(directory):
    try:
        os.makedirs(directory)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


# -- Access control test case ----

class TestAccess(unittest.TestCase):
    """Test SSO based access control for tables and associated data files.
    """
    def setUp(self):
        self.base_url = os.environ['IBE_UNITTEST_BASE_URL']

    def _do_test(self, table):
        base_url = os.path.join(self.base_url, 'search', table) + '?ct=csv'
        # Note: the relational constrains are chosen such that they do
        # not filter out any test records.
        queries = [
            # positional query
            base_url + '&POS=0,0',
            # relational query
            base_url + '&where=x%3C10',
            # position query with relational constraint
            base_url + '&POS=0,0&where=x%3E-10',
        ]
        print ''
        print 'Testing access to ' + table

        # check search results
        for query in queries:
            print '\ttesting %s ...' % query
            for user in users:
                print '\tuser ' + user.name
                results = ibe_run_search(self, user, query)
                result_ids = sorted(map(int, [r['id'] for r in results]))
                expected_ids = sorted([r.id for r in get_expected_results(table, user)])
                self.assertEqual(expected_ids, result_ids, msg='Query results are '
                    'missing expected rows and/or contain unexpected rows.')

        print '\ttesting file/directory access ...'
        files = [r.path for r in records]
        dirs = set()
        for f in files:
            f = os.path.split(f)[0]
            while f:
                dirs.add(f)
                f = os.path.split(f)[0]
        dirs.add('')
        base_url = os.path.join(self.base_url, 'data', table)
        for user in users:
            print '\tuser ' + user.name
            # check file access
            for f in files:
                url = os.path.join(base_url, f)
                expected = get_expected_results(table, user, f)
                self.assertTrue(len(expected) <= 1)
                results = ibe_get_data(self, user, url)
                if len(expected) == 0:
                    self.assertTrue(results is None,
                        'access to %s should have been denied' % f)
                else:
                    self.assertTrue(results is not None,
                        'access to %s should have been allowed' % f)
            # check directory listings
            for d in dirs:
                url = os.path.join(base_url, d)
                results = scrape_dir_contents(ibe_get_data(self, user, url))
                expected = set()
                for r in get_expected_results(table, user, d):
                    path = r.path[len(d):]
                    if path[0] == '/':
                        path = path[1:]
                    i = path.find('/')
                    if i != -1:
                        path = path[:i+1]
                    expected.add(path)
                if len(expected) == 0 and d != '':
                    self.assertTrue(results is None,
                        'access to %s should have been denied' % d)
                else:
                    self.assertEqual(expected, results,
                        'directory listing for /%s does not match expectations' % d)

    def test_access_granted(self):
        self._do_test('unittest/access/granted')
    def test_access_denied(self):
        self._do_test('unittest/access/denied')
    def test_access_table(self):
        self._do_test('unittest/access/table')
    def test_access_row_only(self):
        self._do_test('unittest/access/row_only')
    def test_access_date_only(self):
        self._do_test('unittest/access/date_only')
    def test_access_row_date(self):
        self._do_test('unittest/access/row_date')


# -- Test data generation ----

def generate_access_data(dialect):
    """Generates SQL DDL for the unittest database table, a chunk index
    to enable spatial search on it, a catalog.xml file to describe the
    unittest table to IBE, and fake FITS files corresponding to each
    row in the table.
    """
    web_test_dir = os.path.abspath(os.path.dirname(__file__))
    bin_dir = os.path.normpath(os.path.join(web_test_dir, os.path.pardir, os.path.pardir, 'bin'))
    ut_dir = os.path.join(web_test_dir, 'unittest')

    # 1. Create a WCS
    # All test images will share this WCS (we are testing access control,
    # not spatial search).
    transform = pywcs.WCS()
    transform.naxis1 = 8
    transform.naxis2 = 8
    transform.wcs.ctype[0] = 'RA---TAN'
    transform.wcs.ctype[1] = 'DEC--TAN'
    transform.wcs.crval = [0.0, 0.0]
    transform.wcs.crpix = [4.5, 4.5]
    del transform.wcs.cd
    transform.wcs.crota = [0.0, 0.0]
    transform.wcs.cdelt = [-0.01, 0.01]
    transform.wcs.set()
    corners = numpy.zeros(shape=(4,2), dtype=numpy.float64)
    corners[0,0] = 0.5
    corners[0,1] = 0.5
    corners[1,0] = 8.5
    corners[1,1] = 0.5
    corners[2,0] = 8.5
    corners[2,1] = 8.5
    corners[3,0] = 0.5
    corners[3,1] = 8.5
    corners = transform.all_pix2sky(corners, 1)

    # 2. Generate SQL DDL / ASCII data dump
    # Informix/Oracle have different types for date-times, and different
    # functions for converting strings to date-time values.
    float_type = 'BINARY_DOUBLE' if dialect=='oracle' else 'DOUBLE PRECISION'
    datetime_type = 'TIMESTAMP' if dialect=='oracle' else 'DATETIME YEAR TO SECOND'
    if dialect=='oracle':
        to_datetime = "TO_TIMESTAMP('YYYY-MM-DD HH24:MI:SS', '{0!s}')"
    else:
        to_datetime = "TO_DATE('{0!s}', '%Y-%m-%d %H:%M:%S')"
    with contextlib.nested(
        open(os.path.join(ut_dir, 'ibe_unittest_access.sql'), 'w'),
        open(os.path.join(ut_dir, 'ibe_unittest_access.bar'), 'w')
    ) as (sql, dump):
        sql.write(str.format(
            'CREATE TABLE ibe_unittest_access (\n'
            '\tid INTEGER NOT NULL PRIMARY KEY,\n'
            '\tipac_gid INTEGER NOT NULL,\n'
            '\tipac_pub_date {1} NOT NULL,\n'
            '\tx INTEGER NOT NULL,\n'
            '\t-- WCS related columns\n'
            '\tnaxis  INTEGER NOT NULL,\n'
            '\tnaxis1 INTEGER NOT NULL,\n'
            '\tnaxis2 INTEGER NOT NULL,\n'
            '\tctype1 CHAR(8) NOT NULL,\n'
            '\tctype2 CHAR(8) NOT NULL,\n'
            '\tcrpix1 {0} NOT NULL,\n'
            '\tcrpix2 {0} NOT NULL,\n'
            '\tcrval1 {0} NOT NULL,\n'
            '\tcrval2 {0} NOT NULL,\n'
            '\tcdelt1 {0} NOT NULL,\n'
            '\tcdelt2 {0} NOT NULL,\n'
            '\tcrota2 {0} NOT NULL,\n'
            '\tra1    {0} NOT NULL,\n'
            '\tdec1   {0} NOT NULL,\n'
            '\tra2    {0} NOT NULL,\n'
            '\tdec2   {0} NOT NULL,\n'
            '\tra3    {0} NOT NULL,\n'
            '\tdec3   {0} NOT NULL,\n'
            '\tra4    {0} NOT NULL,\n'
            '\tdec4   {0} NOT NULL,\n'
            '\tpath   CHAR(32) NOT NULL\n'
            ');\n', float_type, datetime_type))
        for record in records:
            # write out insert statement for the record
            sql.write(str.format(
                "INSERT INTO ibe_unittest_access VALUES (\n"
                "  {id},\n"
                "  {gid},\n"
                "  {pubdate},\n"
                "  {x},\n"
                "  2,\n"
                "  8,\n"
                "  8,\n"
                "  'RA---TAN',\n"
                "  'DEC--TAN',\n"
                "   4.5,\n"
                "   4.5,\n"
                "   0.0,\n"
                "   0.0,\n"
                "  -0.01,\n"
                "   0.01,\n"
                "   0.0,\n"
                "   {corners[0][0]!r},\n"
                "   {corners[0][1]!r},\n"
                "   {corners[1][0]!r},\n"
                "   {corners[1][1]!r},\n"
                "   {corners[2][0]!r},\n"
                "   {corners[2][1]!r},\n"
                "   {corners[3][0]!r},\n"
                "   {corners[3][1]!r},\n"
                "   {path!r}\n"
                ");\n",
                id=record.id,
                gid=record.gid,
                pubdate=str.format(to_datetime, record.pubdate),
                x=record.x,
                path=record.path,
                corners=corners))
            # write out bar-delimited version of the record
            dump.write(str.format(
                '{id}|{gid}|{pubdate!s}|{x}|'
                '2|8|8|RA---TAN|DEC--TAN|4.5|4.5|0.0|0.0|-0.01|0.01|0.0|'
                '{corners[0][0]!r}|{corners[0][1]!r}|'
                '{corners[1][0]!r}|{corners[1][1]!r}|'
                '{corners[2][0]!r}|{corners[2][1]!r}|'
                '{corners[3][0]!r}|{corners[3][1]!r}|'
                '{path!s}|\n',
                id=record.id,
                gid=record.gid,
                pubdate=record.pubdate,
                x=record.x,
                path=record.path,
                corners=corners))

    # 3. Generate chunk index
    chunk_index = os.path.join(os.environ['CM_STK_DIR'], 'bin', 'chunk_index.py')
    # identical to the columns in the DDL above
    columns = ('id,ipac_gid,ipac_pub_date,x,naxis,naxis1,naxis2,'
               'ctype1,ctype2,crpix1,crpix2,crval1,crval2,cdelt1,cdelt2,crota2,'
               'ra1,dec1,ra2,dec2,ra3,dec3,ra4,dec4,path')
    chunk_index_dir = os.path.join(ut_dir, 'chunk_index')
    shutil.rmtree(os.path.join(chunk_index_dir, 'unittest', 'access'), ignore_errors=True)
    args = [
        chunk_index,
        '--kind=tiny', '-z', '-i',
        # units for each column
        '-u', (',,,,,pix,pix,,,pix,pix,deg,deg,deg/pix,deg/pix,'
               'deg,deg,deg,deg,deg,deg,deg,deg,deg,'),
        # IPAC ASCII data type for each column
        '-t', ('int,int,char,int,int,int,int,char,char,double,double,'
               'double,double,double,double,double,double,double,double,'
               'double,double,double,double,double,char'),
        '-C', columns,
        # crval[12] correspond to the image center
        '-U', 'id', '-T', 'crval1', '-P', 'crval2',
        'create', 'unittest', 'access', chunk_index_dir,
        columns,
        # the ASCII dump produced in 2.
        os.path.join(ut_dir, 'ibe_unittest_access.bar'),
    ]
    subprocess.check_call(args)

    # 4. Generate fake FITS files
    access_data_dir = os.path.join(ut_dir, 'data', 'access')
    shutil.rmtree(access_data_dir, ignore_errors=True)
    # 8x8 image filled with zeroes, and WCS header keywords matching the
    # parameters used in step 1.
    hdu = pyfits.PrimaryHDU(numpy.zeros(shape=(8,8), dtype=numpy.float32))
    hdu.header.update('CTYPE1', 'RA---TAN')
    hdu.header.update('CTYPE2', 'DEC--TAN')
    hdu.header.update('CRVAL1', 0.0)
    hdu.header.update('CRVAL2', 0.0)
    hdu.header.update('CRPIX1', 4.5)
    hdu.header.update('CRPIX2', 4.5)
    hdu.header.update('CDELT1', -0.01)
    hdu.header.update('CDELT2', 0.01)
    hdu.header.update('CROTA2', 0.0)
    for r in records:
        path = os.path.join(access_data_dir, r.path)
        ensure_dir_exists(os.path.dirname(path))
        # include ID and access control info in header; other
        # than that each image is identical
        hdu.header.update('IBE_ID', r.id)
        hdu.header.update('IBE_GID', r.gid)
        hdu.header.update('IBE_PDAT', r.pubdate.isoformat())
        hdu.writeto(path)

    # 5. Generate file system metadata
    fsdb_dir = os.path.join(ut_dir, 'fsdb', 'access')
    if os.path.exists(fsdb_dir):
        shutil.rmtree(fsdb_dir)
    os.makedirs(fsdb_dir)
    fsdb = os.path.join(fsdb_dir, 'fsdb.sqlite3')
    with open(os.path.join(fsdb_dir, 'input.bar'), 'wb') as f:
        for r in sorted(records, key=lambda x: x.path):
            f.write('|'.join(map(str, (r.path, r.gid, r.pubdate,))))
            f.write('\n')
    args = [
         os.path.join(bin_dir, 'gen_fsdb.py'),
         '--scratch-dir',
         fsdb_dir,
         '--output',
         fsdb,
         '--input',
         os.path.join(fsdb_dir, 'input.bar'),
    ]
    subprocess.check_call(args, shell=False)

    # 6. Generate XML config file for access unit tests.
    access_conf_dir = os.path.join(
        web_test_dir, os.pardir, os.pardir, 'conf', 'catalogs', 'unittest', 'access')
    ensure_dir_exists(access_conf_dir)
    with open(os.path.join(access_conf_dir, 'catalogs.xml'), 'wb') as f:
        f.write(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '\n'
            '<catalogs>\n'
            '<schema_group id="unittest">\n'
            '<schema name="access" engine="unittest_access">\n'
            '  <description>Tables for unit testing SSO-based access control</description>\n'
            '\n'
        )
        for name in ('granted', 'denied', 'table', 'row_only', 'date_only', 'row_date'):
            NAME = name.upper()
            ancillary = ''
            if name == 'table':
                ancillary = 'group="2"'
            elif name not in ('granted', 'denied'):
                ancillary = 'group="0" fsdb="{0}"'.format(fsdb)
            f.write(str.format(
                '  <table name="{name}" dbname="ibe_unittest_access">\n'
                '    <description>ACCESS_{NAME} test table</description>\n'
                '    <chunk_index path="{chunk_index_path}" />\n'
                '    <corners radius="0.5" />\n'
                '    <center ra="crval1" dec="crval2"/>\n'
                '    <unique refs="id" />\n'
                '    <products rootpath="{product_root_path}" />\n'
                '    <access policy="ACCESS_{NAME}" {ancillary} mission="200" />\n',
                name=name,
                NAME=NAME,
                chunk_index_path=os.path.join(chunk_index_dir, 'unittest', 'access', 'index.ci'),
                product_root_path=access_data_dir,
                ancillary=ancillary,
            ))
            f.write(
                '    <column name="id" principal="true">\n'
                '      <description />\n'
                '      <datatype>INTEGER</datatype>\n'
                '    </column>\n'
                '    <column name="ipac_gid" principal="true">\n'
                '      <description />\n'
                '      <datatype>INTEGER</datatype>\n'
                '    </column>\n'
                '    <column name="ipac_pub_date" principal="true">\n'
                '      <description />\n'
                '      <datatype>DATETIME</datatype>\n'
                '    </column>\n'
                '    <column name="x">\n'
                '      <description />\n'
                '      <datatype>INTEGER</datatype>\n'
                '    </column>\n'
                '    <column name="naxis">\n'
                '      <description />\n'
                '      <ucd>pos.wcs.naxes</ucd><utype>fits:NAXIS</utype>\n'
                '      <datatype>INTEGER</datatype><format_spec>1d</format_spec>\n'
                '    </column>\n'
                '    <column name="naxis1" principal="true">\n'
                '      <description />\n'
                '      <ucd>pos.wcs.naxis</ucd><utype>fits:NAXIS1</utype><unit>pix</unit>\n'
                '      <datatype>INTEGER</datatype><format_spec>4d</format_spec>\n'
                '    </column>\n'
                '    <column name="naxis2" principal="true">\n'
                '      <description />\n'
                '      <ucd>pos.wcs.naxis</ucd><utype>fits:NAXIS2</utype><unit>pix</unit>\n'
                '      <datatype>INTEGER</datatype><format_spec>4d</format_spec>\n'
                '    </column>\n'
                '    <column name="ctype1">\n'
                '      <description />\n'
                '      <ucd>pos.wcs.ctype</ucd><utype>fits:CTYPE1</utype>\n'
                '      <datatype>CHAR(8)</datatype>\n'
                '    </column>\n'
                '    <column name="ctype2">\n'
                '      <description />\n'
                '      <ucd>pos.wcs.ctype</ucd><utype>fits:CTYPE2</utype>\n'
                '      <datatype>CHAR(8)</datatype>\n'
                '    </column>\n'
                '    <column name="crpix1">\n'
                '      <description />\n'
                '      <ucd>pos.wcs.crpix</ucd><utype>fits:CRPIX1</utype><unit>pix</unit>\n'
                '      <datatype>DOUBLE</datatype><format_spec>10.5f</format_spec>\n'
                '    </column>\n'
                '    <column name="crpix2">\n'
                '      <description />\n'
                '      <ucd>pos.wcs.crpix</ucd><utype>fits:CRPIX2</utype><unit>pix</unit>\n'
                '      <datatype>DOUBLE</datatype><format_spec>10.5f</format_spec>\n'
                '    </column>\n'
                '    <column name="crval1">\n'
                '      <description />\n'
                '      <ucd>pos.wcs.crval</ucd><utype>fits:CRVAL1</utype><unit>deg</unit>\n'
                '      <datatype>DOUBLE</datatype><format_spec>11.7f</format_spec>\n'
                '    </column>\n'
                '    <column name="crval2">\n'
                '      <description />\n'
                '      <ucd>pos.wcs.crval</ucd><utype>fits:CRVAL2</utype><unit>deg</unit>\n'
                '      <datatype>DOUBLE</datatype><format_spec>11.7f</format_spec>\n'
                '    </column>\n'
                '    <column name="cdelt1">\n'
                '      <description />\n'
                '      <utype>fits:CDELT1</utype><unit>deg/pix</unit>\n'
                '      <datatype>DOUBLE</datatype>\n'
                '    </column>\n'
                '    <column name="cdelt2">\n'
                '      <description />\n'
                '      <utype>fits:CDELT2</utype><unit>deg/pix</unit>\n'
                '      <datatype>DOUBLE</datatype>\n'
                '    </column>\n'
                '    <column name="crota2">\n'
                '      <description />\n'
                '      <utype>fits:CROTA2</utype><unit>deg</unit>\n'
                '      <datatype>DOUBLE</datatype>\n'
                '    </column>\n'
            )
            # 4 corner columns
            for i in range(1,5):
                for col in ('ra', 'dec'):
                    f.write(str.format(
                        '    <column name="{0}{1}" principal="true">\n'
                        '      <description />\n'
                        '      <datatype>DOUBLE</datatype>\n'
                        '      <format_spec>13.9f</format_spec>\n'
                        '      <ucd>pos.eq.dec</ucd>\n'
                        '      <unit>deg</unit>\n'
                        '    </column>\n',
                        col, i
                    ))
            f.write(
                '  </table>\n'
                '\n'
            )
        f.write(
            '</schema>\n'
            '</schema_group>\n'
            '</catalogs>\n'
        )


# -- Program entry point ----

if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option(
        '-p', '--port', dest='port', metavar='PORT', type='int', default=80,
        help='Port number of the IBE instance to test (%default)')
    parser.add_option(
        '-H', '--host', dest='host', metavar='HOST', type='string',
        default=socket.getfqdn(),
        help='Fully-qualified hostname of the IBE instance to test (%default)')
    parser.add_option(
        '-g', '--generate-data', action='store_true', dest='generate_data',
        default=False,
        help='Generate SQL DDL, catalog.xml, chunk indexes, file '
             'system metadata and FITS files for the unit test table. '
             'Omitting this will run unit tests instead.')
    parser.add_option(
        '-d', '--dialect', dest='dialect', metavar='DIALECT', type='string',
        default='informix',
        help='SQL dialect of generated DD - "informix" (the default) and '
             '"oracle" are supported. This option is ignored unless '
             '--generate-data is specified.')
    (options, args) = parser.parse_args()
    if options.generate_data:
        if not os.environ.get('CM_BASE_DIR', ''):
            parser.error('CM_BASE_DIR environment variable undefined or empty')
        if not os.environ.get('CM_STK_DIR', ''):
            parser.error('CM_STK_DIR environment variable undefined or empty')
        generate_access_data(options.dialect.lower())
    else:
        os.environ['IBE_UNITTEST_BASE_URL'] = 'http://%s:%d' % (options.host, options.port)
        suite = unittest.TestLoader().loadTestsFromTestCase(TestAccess)
        unittest.TextTestRunner(verbosity=2).run(suite)

