#! /usr/bin/env python
import csv
import cx_Oracle as sql
import optparse
import os
import os.path
import re
import subprocess
import sys
import tempfile

from contextlib import closing


dialect = {
    'skipinitialspace': False,
    'doublequote': False,
    'escapechar': '\\',
    'delimiter': '|',
    'quotechar': '"',
    'lineterminator' : '\n',
    'quoting': csv.QUOTE_NONE
}

level2_filename_re = re.compile(
    r'^PTF_(?P<ptffield>d\d{6})_(?P<fid>f\d{2})_(?P<ccdid>c\d{2})_')


def write_paths(conn_string, table, writer):
    """Writes paths (each with a group ID and publication date)
    to the given CSV writer.
    """
    # query extracts all columns containing file names from the PTF
    # reference image table.
    query = str.format('SELECT'
                       ' filename,'
                       ' rawpsffilename,'
                       ' psfgridfilename,'
                       ' psfds9regfilename,'
                       ' depthfilename,'
                       ' uncfilename,'
                       ' sexrfcatfilename,'
                       ' psfrfcatfilename,'
                       ' ipac_gid, ipac_pub_date '
                       'FROM {0}', table)
    # always_private indicates which of the file name columns above should
    # be treated as private, regardless of ipac_gid and ipac_pub_date.
    always_private = (False,)*8
    with closing(sql.connect(conn_string)) as conn:
        with closing(conn.cursor()) as cursor:
            cursor.execute(query)
            row = cursor.fetchone()
            while row is not None:
                ipac_gid = row[8]
                ipac_pub_date = row[9]
                for i in xrange(8):
                    f = row[i]
                    # Ignore files that do not have the expected format
                    if f == None:
                        continue
                    f = f.strip()
                    m = re.match(level2_filename_re, f)
                    if not m:
                        continue
                    # Construct path relative to link tree from filename
                    f = os.path.join(m.group('ptffield')[:4],
                                     m.group('ptffield'),
                                     m.group('fid'),
                                     m.group('ccdid'),
                                     f)
                    if always_private[i]:
                        # Hide away private files
                        writer.writerow((f, '100', '9999-12-31 23:59:59.999000'))
                    else:
                        writer.writerow((f, ipac_gid, ipac_pub_date))
                row = cursor.fetchone()


def main():
    parser = optparse.OptionParser("""
        %prog [options] <connection_string> <table_name>

        Connects to an oracle database using the specified connection string
        and writes file-system metadata from the given PTF reference image
        metadata table to standard out. Note that <connection_string> is
        expected to be of the form:

            user/password@dsn

        which is the same format used by Oracle applications such as SQL*Plus.
        The output consist of lines in the following format:

        <path>|<IPAC group ID>|<publication date>

        sorted in ascending <path> order (as required by gen_fsdb.py).
        """)
    parser.add_option(
        '-s', '--scratch-dir', type='string', dest='scratch_dir',
        default=os.environ.get('TMPDIR', '/tmp'),
        help='Scratch directory name; defaults to $TMPDIR and '
             'falls back to /tmp (%default)')
    ns, inputs = parser.parse_args()
    if len(inputs) != 2:
        parser.error('Invalid argument count; a connection string '
                     'and table name are required.')
    with closing(tempfile.TemporaryFile(dir=ns.scratch_dir)) as t:
        write_paths(inputs[0], inputs[1], csv.writer(t, **dialect))
        t.seek(0)
        # Make sure UNIX sort and python string comparisons agree
        env = os.environ.copy()
        env['LC_COLLATE'] = 'C'
        subprocess.call(
            ['sort', '--unique',  '--temporary-directory=' + ns.scratch_dir],
            env=env, shell=False, stdin=t, stdout=sys.stdout, stderr=sys.stderr)
        sys.stdout.flush()

if __name__ == "__main__":
    main()

