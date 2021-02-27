#! /usr/bin/env python
import csv
import cx_Oracle as sql
import optparse
import os.path
import sys

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


def write_sorted_paths(conn_string, table, writer):
    """Writes paths (each with a group ID and publication date)
    in ascending order to the given CSV writer.

    Note: calibration files may eventually have to be included; their
    file names (but not full paths) are given by the l1idbias, l1iddark,
    and l1idflat columns (and possibly others).

    In that case, paths will have to be sorted in a post-processing step
    (e.g. using the UNIX sort command), and not by the RDBMS.
    """
    query = str.format('SELECT filehand, ipac_gid, ipac_pub_date '
                       'FROM {0} ORDER BY filehand', table)
    with closing(sql.connect(conn_string)) as conn:
        with closing(conn.cursor()) as cursor:
            cursor.execute(query)
            row = cursor.fetchone()
            while row is not None:
                filehand = row[0]
                assert filehand != None
                filehand = filehand.strip()
                assert len(filehand) > 0 and os.path.isabs(filehand)
                ipac_gid = row[1]
                ipac_pub_date = row[2]
                f, ext = os.path.splitext(filehand)
                assert ext == '.fits'
                # Each image metadata table entry may have an associated
                # ancillary file, preview JPEG/PNG, and catalog of source
                # extractions.
                writer.writerow((f + '.anc', ipac_gid, ipac_pub_date))
                writer.writerow((filehand, ipac_gid, ipac_pub_date))
                writer.writerow((f + '.jpg', ipac_gid, ipac_pub_date))
                writer.writerow((f + '.png', ipac_gid, ipac_pub_date))
                writer.writerow((f + '_cat.fits', ipac_gid, ipac_pub_date))
                row = cursor.fetchone()

def main():
    parser = optparse.OptionParser("""
        %prog [options] <connection_string> <table_name>

        Connects to an oracle database using the specified connection string
        and writes file-system metadata from the given LCOGT image metadata
        table to standard out. Note that <connection_string> is expected to
        be of the form:

            user/password@dsn

        which is the same format used by Oracle applications such as SQL*Plus.
        The output consist of lines in the following format:

        <path>|<IPAC group ID>|<publication date>

        sorted in ascending <path> order (as required by gen_fsdb.py).
        """)
    ns, inputs = parser.parse_args()
    if len(inputs) != 2:
        parser.error('Invalid argument count; a connection string '
                     'and table name are required.')
    write_sorted_paths(inputs[0], inputs[1], csv.writer(sys.stdout, **dialect))
    sys.stdout.flush()

if __name__ == "__main__":
    main()
