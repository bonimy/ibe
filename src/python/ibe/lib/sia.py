import abc
import itertools
import math
import numpy
from routes import url_for


_seconds_per_day = 86400.0


class VotValues(object):
    def __init__(self, values, legal=False):
        self._type = "legal" if legal else "actual"
        if isinstance(values, (tuple,list,set)):
            self._vals = dict(itertools.izip(values, itertools.repeat(None)))
        else:
            self._vals = dict(values)

    def write(self, out):
        out.write('\t\t<VALUES type="%s">\n' % self._type)
        for k in self._vals:
            out.write('\t\t\t<OPTION')
            v = self._vals[k]
            if v is not None and len(v) > 0:
                out.write(' name="%s"' % v)
            out.write(' value="%s"/>\n' % k)
        out.write('\t\t</VALUES>\n')

def _vot_param(out, name, datatype, value,
               arraysize=None, ucd=None, unit=None,
               description=None, values=None):
    out.write('\t<PARAM name="%s" datatype="%s"' % (name, datatype))
    if arraysize is not None and arraysize != 1:
        out.write(' arraysize="%s"' % arraysize)
    out.write(' value="%s"' % value)
    if ucd is not None:
        out.write(' ucd="%s"' % ucd)
    if unit is not None:
        out.write(' unit="%s"' % unit)
    nested = False
    if description is not None and len(description) > 0:
        nested = True
        out.write('>\n\t\t<DESCRIPTION>')
        out.write(description)
        out.write('\n\t\t</DESCRIPTION>\n')
    if values is not None:
        if not nested:
            out.write('>\n')
        nested = True
        values.write(out)
    if nested:
        out.write('\t</PARAM>\n')
    else:
        out.write('/>\n')

def _vot_field(out, name, datatype, arraysize=None, ucd=None, unit=None,
               description=None, values=None):
    out.write('\t<FIELD name="%s" datatype="%s"' % (name, datatype))
    if arraysize is not None and arraysize != 1:
        out.write(' arraysize="%s"' % arraysize)
    if ucd is not None:
        out.write(' ucd="%s"' % ucd)
    if unit is not None:
        out.write(' unit="%s"' % unit)
    nested = False
    if description is not None and len(description) > 0:
        nested = True
        out.write('>\n\t\t<DESCRIPTION>')
        out.write(description)
        out.write('\n\t\t</DESCRIPTION>\n')
    if values is not None:
        if not nested:
            out.write('>\n')
        nested = True
        values.write(out)
    if nested:
        out.write('\t</FIELD>\n')
    else:
        out.write('/>\n')

def _sia_in_params(out):
    _vot_param(
        out,
        name='INPUT:POS',
        datatype='char',
        arraysize='*',
        value='0,0',
        description='''\
Search region center in the form "ra,dec" where the right ascension
ra and declination dec are given in decimal degrees in the ICRS coordinate
system. Embedded whitespace is not allowed.''',
    )
    _vot_param(
        out,
        name='INPUT:SIZE',
        datatype='char',
        arraysize='*',
        value='0',
        description='''\
Search region angular width/height in the form "size_ra,size_dec" or "size".
If a single number is provided, it is used as both the width and the height.
The search region center (POS) defines the center of a TAN projection with
the standard (N,E) basis; size_ra specifies the angular width along the E
axis, and size_dec the angular height along the N axis. A special case is
SIZE=0 or SIZE=0,0. This is equivalent to searching for all images
overlapping POS (so long as INTERSECT is not ENCLOSED).''',
    )
    _vot_param(
        out,
        name='INPUT:INTERSECT',
        datatype='char',
        arraysize='*',
        value='OVERLAPS',
        description='''\
A parameter that indicates how matched images should intersect the search
region R. A value of COVERS means that returned images cover (include) R,
ENCLOSED means that returned images are completely inside R, CENTER means
that returned images contain the center of R (POS), and OVERLAPS, the default,
means that returned images overlap R. Note that the search region boundary
consists of great circles by construction, and images are approximated by
connecting their corners with great circles. Intersection tests of the
resulting sky-polygons are performed without further approximation.''',
        values=VotValues(['CENTER', 'COVERS', 'ENCLOSED', 'OVERLAPS'], legal=True),
    )
    _vot_param(
        out,
        name='INPUT:FORMAT',
        datatype='char',
        arraysize='*',
        value='image/fits',
        description='''\
Requested output format. ALL or image/fits will return images matching the
search region according to the spatial predicate given by INTERSECT, and a
value of FORMAT will return metadata about this data-set. Any other value
will result in an error. In particular, GRAPHIC formats are not supported
by this service.''',
        values=VotValues(['ALL', 'FORMAT', 'image/fits']),
    )
    _vot_param(
        out,
        name='INPUT:mcen',
        datatype='char',
        arraysize='*',
        value='true',
        description='''\
If this parameter is passed with any value whatsoever, INTERSECT=CENTER
and/or SIZE=0, then the image most centered on the search region center
is returned (rather than all images containing the center).''',
    )

def _open_sia(out):
    out.write("""\
<?xml version="1.0"?>
<VOTABLE version="1.2"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xmlns="http://www.ivoa.net/xml/VOTable/v1.2" >
<RESOURCE type="results">
\t<INFO name="QUERY_STATUS" value="OK"/>
""")
    _sia_in_params(out)

def _open_table(out):
    out.write('<TABLE>\n')

    # fields
    _vot_field(out, name='sia_title',
        datatype='char', arraysize='*', ucd='VOX:Image_Title',
        description='Concise description of the image returned',
    )
    _vot_field(out, name='sia_url',
        datatype='char', arraysize='*', ucd='VOX:Image_AccessReference',
        description='Image access reference URL.',
    )
    _vot_field(out, name='sia_naxes',
        datatype='int', ucd='VOX:Image_Naxes',
        description='Number of Image Axes',
    )
    _vot_field(out, name='sia_fmt',
        datatype='char', arraysize='*', ucd='VOX:Image_Format',
        description='MIME-type of the object pointed to by the image access reference URL',
    )
    _vot_field(out, name='sia_ra',
        datatype='double', unit='deg', ucd='POS_EQ_RA_MAIN',
        description='ICRS right-ascension of the image center.',
    )
    _vot_field(out, name='sia_dec',
        datatype='double', unit='deg', ucd='POS_EQ_DEC_MAIN',
        description='ICRS declination of the image center.',
    )
    _vot_field(out, name='sia_naxis',
        datatype='int', arraysize='*', ucd='VOX:Image_Naxis',
        description='The image size in pixels along each axis',
    )
    _vot_field(out, name='sia_crpix',
        datatype='double', arraysize='*', unit='pix', ucd='VOX:WCS_CoordRefPixel',
        description='Image pixel coordinates of the WCS reference pixel.',
    )
    _vot_field(out, name='sia_crval',
        datatype='double', arraysize='*', unit='deg', ucd='VOX:WCS_CoordRefValue',
        description='World coordinates of the WCS reference pixel.',
    )
    _vot_field(out, name='sia_proj',
        datatype='char', arraysize=3, ucd='VOX:WCS_CoordProjection',
        description='three character celestial projection code'
    )
    _vot_field(out, name='sia_scale',
        datatype='double', arraysize='*', unit='deg/pix', ucd='VOX:Image_Scale',
        description='The scale of each image axis in degrees per pixel',
    )
    _vot_field(out, name='sia_cd',
        datatype='double', arraysize='*', unit='deg/pix', ucd='VOX:WCS_CDMatrix',
        description='WCS CD matrix.',
    )


class SiaWriterBase(object):
    """Writer for producing SIA VO tables.
    """
    def __init__(self, out, table, columns, server, url_root):
        self.out = out
        self.have_data = False
        self.table = table
        self.root_url = '/'.join([server + url_root, 'data', table.id().replace('.', '/')])
        # write out common header bits
        _open_sia(out)
        _open_table(out)

    @staticmethod
    def get_required_cols(table):
        columns = []
        if table.wcsutils:
            columns.extend(table.wcsutils.columns)
        if table.center:
            columns.extend(table.center.columns)
        return columns

    @staticmethod
    def content_type():
        return 'application/x-votable+xml; charset=UTF-8'

    @abc.abstractmethod
    def get_title(self, row):
        """Returns a title for the image corresponding to a row.
        """

    @abc.abstractmethod
    def get_url(self, row):
        """Returns a URL for the FITS image corresponding to this row.
        """

    def write_field_c(self, row, column):
        self.out.write('<TD>')
        self.out.write(column.type.to_ascii(row[column.dbname], '').strip())
        self.out.write('</TD>\n')

    def write_field_v(self, value):
        self.out.write('<TD>')
        self.out.write(value)
        self.out.write('</TD>\n')

    def start_row(self, row, computed_row):
        o = self.out
        t = self.table
        w = t.wcsutils
        if not self.have_data:
            o.write('<DATA><TABLEDATA>\n\t')
            self.have_data = True
        o.write('<TR>\n')
        # image title
        o.write('<TD>')
        o.write(self.get_title(row))
        o.write('</TD>\n<TD>')
        # image URL
        o.write(self.get_url(row))
        # for now, only support FITS images with NAXIS=2
        o.write('</TD>\n<TD>2</TD>\n<TD>image/fits</TD>\n<TD>') 
        # center ra and dec
        ra = t.center.columns[0]
        dec = t.center.columns[1]
        if t.center.computed:
            o.write(ra.type.to_ascii(computed_row[ra.dbname], '').strip())
            o.write('</TD>\n<TD>')
            o.write(dec.type.to_ascii(computed_row[dec.dbname], '').strip())
        else:
            o.write(ra.type.to_ascii(row[ra.dbname], '').strip())
            o.write('</TD>\n<TD>')
            o.write(dec.type.to_ascii(row[dec.dbname], '').strip())
        o.write('</TD>\n<TD>')
        # naxis1 and naxis2
        o.write(w.naxis1.type.to_ascii(w.naxis1.get(row)).strip())
        o.write(' ')
        o.write(w.naxis2.type.to_ascii(w.naxis2.get(row)).strip())
        o.write('</TD>\n<TD>')
        # crpix
        o.write(w.crpix1.type.to_ascii(w.crpix1.get(row)).strip())
        o.write(' ')
        o.write(w.crpix2.type.to_ascii(w.crpix2.get(row)).strip())
        o.write('</TD>\n<TD>')
        # crval
        o.write(w.crval1.type.to_ascii(w.crval1.get(row)).strip())
        o.write(' ')
        o.write(w.crval2.type.to_ascii(w.crval2.get(row)).strip())
        o.write('</TD>\n<TD>')
        # projection type
        o.write(w.ctype1.get(row)[5:8])
        o.write('</TD>\n<TD>')
        if not w.have_cd:
            # cdelt
            cdelt1 = w.cdelt1.get(row)
            cdelt2 = w.cdelt2.get(row)
            o.write(w.cdelt1.type.to_ascii(cdelt1).strip())
            o.write(' ')
            o.write(w.cdelt2.type.to_ascii(cdelt2).strip())
            o.write('</TD>\n<TD>')
            # derive CD from cdelt and PC or CROTA2
            cdelt1 = float(cdelt1)
            cdelt2 = float(cdelt2)
            if w.have_pc:
                # See FITS Paper I
                cd1_1 = float(w.pc1_1.get(row))*cdelt1
                cd1_2 = float(w.pc1_2.get(row))*cdelt1
                cd2_1 = float(w.pc2_1.get(row))*cdelt2
                cd2_2 = float(w.pc2_2.get(row))*cdelt2
            else:
                # See 6.1 of FITS Paper II
                crota2 = 0.0
                if w.have_rot:
                    crota2 = math.radians(float(w.crota2.get(row)))
                sin_crota2 = math.sin(crota2)
                cos_crota2 = math.cos(crota2)
                cd1_1 =  cos_crota2*cdelt1
                cd1_2 = -sin_crota2*cdelt2
                cd2_1 =  sin_crota2*cdelt1
                cd2_2 =  cos_crota2*cdelt2
            o.write(repr(cd1_1))
            o.write(' ')
            o.write(repr(cd1_2))
            o.write(' ')
            o.write(repr(cd2_1))
            o.write(' ')
            o.write(repr(cd2_2))
        else:
            # derive cdelt from cd matrix
            cd = numpy.zeros(shape=(2,2), dtype=numpy.float64)
            rcd = numpy.zeros(shape=(2,2), dtype=numpy.float64)
            cd1_1 = w.cd1_1.get(row)
            cd1_2 = w.cd1_2.get(row)
            cd2_1 = w.cd2_1.get(row)
            cd2_2 = w.cd2_2.get(row)
            cd[0,0] = float(cd1_1)
            cd[0,1] = float(cd1_2)
            cd[1,0] = float(cd2_1)
            cd[1,1] = float(cd2_2)
            try:
                rho = math.atan2(-cd[0,1], cd[1,1])
                cos_rho = math.cos(rho)
                sin_rho = math.sin(rho)
                rcd[0,0] = cos_rho*cd[0,0] + sin_rho*cd[1,0]
                rcd[0,1] = cos_rho*cd[0,1] + sin_rho*cd[1,1]
                rcd[1,0] = cos_rho*cd[1,0] - sin_rho*cd[0,0]
                rcd[1,1] = cos_rho*cd[1,1] - sin_rho*cd[0,1]
                beta = math.asin(-rcd[1,0]/rcd[0,0]) # skew
                cdelt1 = rcd[0,0]*math.cos(beta)
                cdelt2 = rcd[1,1]
                o.write(repr(rcd[0,0]*math.cos(beta)))
                o.write(' ')
                o.write(repr(rcd[1,1]))
            except:
                # CD matrix is very skewed - i.e. not well
                # approximated by a scaling and a rotation.
                pass
            o.write('</TD>\n<TD>')
            # CD matrix
            o.write(w.cd1_1.type.to_ascii(cd1_1).strip())
            o.write(' ')
            o.write(w.cd1_2.type.to_ascii(cd1_2).strip())
            o.write(' ')
            o.write(w.cd2_1.type.to_ascii(cd2_1).strip())
            o.write(' ')
            o.write(w.cd2_2.type.to_ascii(cd2_2).strip())
        o.write('</TD>\n')

    def end_row(self):
        self.out.write('\n\t</TR>')

    def close(self):
        if self.have_data:
            self.out.write('\n</TABLEDATA></DATA>')
        self.out.write('\n</TABLE></RESOURCE></VOTABLE>\n')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class WiseSiaWriter(SiaWriterBase):
    """SIA VO table output for WISE.
    """
    _bp_ref = [3.35, 4.60, 11.56, 22.09]
    _bp_lo = [3.13, 4.02,  7.60, 19.84]
    _bp_hi = [3.78, 5.19, 16.27, 23.36]

    def __init__(self, out, table, columns, server, url_root):
        super(WiseSiaWriter, self).__init__(out, table, columns, server, url_root)
        self.level1 = (table.name.find("1bm") != -1)
        self.title_prefix = table.description.replace('Images', '').strip()
        self.mjd_obs = None
        self.magzp = table['magzp']
        self.magzpunc = table['magzpunc']
        # parameters
        _vot_param(out, name='sia_pixflags',
            datatype='char', arraysize='*', value='CZ', ucd='VOX:Image_PixFlags',
            description='Image pixels are copied from a source image without change and contain valid flux (intensity) values.',
        )
        _vot_param(out, name='sia_radesys',
            datatype='char', arraysize='*', value='FK5', ucd='VOX:STC_CoordRefFrame',
            description='Coordinate system reference frame',
        )
        _vot_param(out, name='sia_equinox',
            datatype='double', value='2000.0', ucd='VOX:STC_CoordEquinox',
            description='Coordinate system equinox',
        )
        _vot_param(out, name='sia_bp_unit',
            datatype='char', arraysize='*', value='meters', ucd='VOX:BandPass_Unit',
            description='Units used to represent spectral values',
        )
        # fields
        if self.level1:
            self.mjd_obs = table['mjd_obs']
            _vot_field(out, name='sia_mjd_obs',
                datatype='double', ucd='VOX:Image_MJDateObs',
                description='Mean modified Julian date of the observation',
            )
        _vot_field(out, name='sia_bp_id',
            datatype='char', arraysize='*', ucd='VOX:BandPass_ID',
            description='Band pass ID',
            values=VotValues(['W1', 'W2', 'W3', 'W4']),
        )
        _vot_field(out, name='sia_bp_ref',
            datatype='double', ucd='VOX:BandPass_RefValue',
            description='Reference wave-length for band pass',
        )
        _vot_field(out, name='sia_bp_hi',
            datatype='double', ucd='VOX:BandPass_HiLimit',
            description='Upper limit of the band pass',
        )
        _vot_field(out, name='sia_bp_lo',
            datatype='double', ucd='VOX:BandPass_LoLimit',
            description='Lower limit of the band pass',
        )
        _vot_field(out, name='magzp',
            datatype='double',
            description='photometric zero-point mag',
        )
        _vot_field(out, name='magzp',
            datatype='double',
            description='1-sigma uncertainty in photometric zero-point mag',
        )
        _vot_field(out, name='unc_url',
            datatype='char', arraysize='*',
            description='URL for uncertainty image',
        )
        if self.level1:
            _vot_field(out, name='mask_url',
                datatype='char', arraysize='*',
                description='URL for mask image',
            )
        else:
            _vot_field(out, name='cov_url',
                datatype='char', arraysize='*',
                description='URL for depth-of-coverage image',
            )

    def write(self, row, computed_row):
        self.start_row(row, computed_row)
        if self.mjd_obs is not None:
            # mjd_obs
            self.write_field_c(row, self.mjd_obs)
        # band pass information
        band = int(row['band'])
        self.write_field_v('W' + str(band))
        self.write_field_v('%.2fe-6' % self._bp_ref[band - 1])
        self.write_field_v('%.2fe-6' % self._bp_hi[band - 1])
        self.write_field_v('%.2fe-6' % self._bp_lo[band - 1])
        # zero point information
        self.write_field_c(row, self.magzp)
        self.write_field_c(row, self.magzpunc)
        # ancillary URLs
        if self.level1:
            self.write_field_v(self.url + '-unc-1b.fits.gz')
            self.write_field_v(self.url + '-msk-1b.fits.gz')
        else:
            self.write_field_v(self.url + '-unc-3.fits.gz')
            self.write_field_v(self.url + '-cov-3.fits.gz')
        self.end_row()

    @staticmethod
    def get_required_cols(table):
        cols = SiaWriterBase.get_required_cols(table)
        cols.append(table['band'])
        cols.append(table['magzp'])
        cols.append(table['magzpunc'])
        if table.name.find("1bm") != -1:
            cols.append(table['mjd_obs'])
            cols.append(table['scan_id'])
            cols.append(table['frame_num'])
        else:
            cols.append(table['coadd_id'])
        return cols

    def get_title(self, row):
        """Returns a title for the image corresponding to a row.
        """
        if self.level1:
            return ' '.join([self.title_prefix,
                             'W%s' % row['band'],
                             'Frame %03d' % int(row['frame_num']),
                             'in scan %s' %  row['scan_id']
                            ])
        else:
            return ' '.join([self.title_prefix,
                            'W%s' % row['band'],
                            'Coadd %s' % row['coadd_id']
                            ])

    def get_url(self, row):
        """Returns a URL for the FITS image corresponding to this row.
        """
        if self.level1:
            frame_num = '%03d' % int(row['frame_num'])
            scan_id = row['scan_id']
            band = str(row['band'])
            self.url = ''.join([self.root_url,
                                 '/', scan_id[-2:],
                                 '/', scan_id,
                                 '/', frame_num,
                                 '/', scan_id, frame_num, '-w', band])
            return self.url + '-int-1b.fits'
        else:
            coadd_id = row['coadd_id']
            coadd_grp = coadd_id[:2]
            coadd_ra = coadd_id[:4]
            band = str(row['band'])
            self.url = ''.join([self.root_url,
                                '/', coadd_grp,
                                '/', coadd_ra,
                                '/', coadd_id,
                                '/', coadd_id, '-w', band])

            return self.url + '-int-3.fits'


class LcogtSiaWriter(SiaWriterBase):
    """SIA VO table output for LCOGT.
    """
    munged_column_names = [
        'filehand',
        'mjd_obs',
        ]
    column_names = [
        'radesys',
        'equinox',
        'filter',
        'instrume',
        'siteid',
        'enclosur',
        'telescop',
        'exptime',
        'propid',
        'groupid',
        'obsid',
        'object',
        'airmass',
        'lco_id',
        'batch_id',
        ]

    def __init__(self, out, table, columns, server, url_root):
        super(LcogtSiaWriter, self).__init__(out, table, columns, server, url_root)
        self.columns = [table[n] for n in self.column_names]
        # parameters
        _vot_param(out, name='sia_pixflags',
            datatype='char', arraysize='*', value='CZ', ucd='VOX:Image_PixFlags',
            description='Image pixels are copied from a source image without change and contain valid flux (intensity) values.',
        )
        # fields
        _vot_field(out, name='sia_mjd_obs',
            datatype='double', ucd='VOX:Image_MJDateObs',
            description='Mean Modified Julian date of the observation',
        )
        _vot_field(out, name='sia_radesys',
            datatype='char', arraysize='*', ucd='VOX:STC_CoordRefFrame',
            description='Coordinate system reference frame',
        )
        _vot_field(out, name='sia_equinox',
            datatype='double', ucd='VOX:STC_CoordEquinox',
            description='Coordinate system equinox',
        )
        _vot_field(out, name='sia_filter',
            datatype='char', arraysize='*', ucd='VOX:BandPass_ID',
            description='Band pass ID',
        )
        _vot_field(out, name='sia_instrument',
            datatype='char', arraysize='*', ucd='INST_ID',
            description='Instrument ID',
        )
        _vot_field(out, name='siteid',   datatype='char',   description='ID code of the observatory site', arraysize='*')
        _vot_field(out, name='enclosur', datatype='char',   description='Name of the telescope enclosure', arraysize='*')
        _vot_field(out, name='telescop', datatype='char',   description='Name of the telescope', arraysize='*')
        _vot_field(out, name='exptime',  datatype='double', description='Exposure time', unit='s')
        _vot_field(out, name='propid',   datatype='char',   description='Proposal ID', arraysize='*')
        _vot_field(out, name='groupid',  datatype='char',   description='Name of the observing group', arraysize='*')
        _vot_field(out, name='obsid',    datatype='char',   description='Observation ID', arraysize='*')
        _vot_field(out, name='object',   datatype='char',   description='Object name', arraysize='*')
        _vot_field(out, name='airmass',  datatype='double', description='Effective mean airmass')
        _vot_field(out, name='lco_id',   datatype='char',   description='Unique ID', arraysize='*')
        _vot_field(out, name='batch_id', datatype='char',   description='Batch ID for the delivered data', arraysize='*')

    def write(self, row, computed_row):
        self.start_row(row, computed_row)
        # mjd_obs in the LCOGT image database table records the observation
        # start time, but the SIA standard wants the mean observation time.
        sia_mjd_obs = row['mjd_obs'] + row['exptime'] / (2.0*_seconds_per_day)
        self.write_field_v('%.8f' % sia_mjd_obs)
        # output remaining columns
        for c in self.columns:
            self.write_field_c(row, c)
        self.end_row()

    @staticmethod
    def get_required_cols(table):
        cols = SiaWriterBase.get_required_cols(table)
        cols.extend(table[n] for n in LcogtSiaWriter.munged_column_names)
        cols.extend(table[n] for n in LcogtSiaWriter.column_names)
        return cols

    def get_title(self, row):
        """Returns a title for the image corresponding to a row.
        """
        return 'LCO image ' + row['lco_id']

    def get_url(self, row):
        """Returns a URL for the FITS image corresponding to this row.
        """
        return '/'.join([self.root_url, row['filehand']])


class PtfLevel1SiaWriter(SiaWriterBase):
    """SIA VO table output for PTF level 1 images.
    """
    munged_column_names = [
        'pid',
        'obsmjd',
        'aexptime',
        'pfilename',
        'rfilename',
        'afilename1',
        'afilename2',
        'afilename3',
        ]
    column_names = [
        'filter',
        'filtersl',
        'ccdid',
        'ptffield',
        'seeing',
        'airmass',
        'moonillf',
        'moonesb',
        'photcalflag',
        'infobits',
        'nid',
        'fieldid',
        'ptfpid',
        'ptfprpi',
        'moonra',
        'moondec',
        'moonphas',
        'moonalt',
        'gain',
        'readnoi',
        'darkcur',
        ]

    def __init__(self, out, table, columns, server, url_root):
        super(PtfLevel1SiaWriter, self).__init__(out, table, columns, server, url_root)
        # fields
        self.columns = [table[n] for n in self.column_names]
        # parameters
        _vot_param(out, name='sia_pixflags',
            datatype='char', arraysize='*', value='CZ', ucd='VOX:Image_PixFlags',
            description='Image pixels are copied from a source image without change and contain valid flux (intensity) values.',
        )
        _vot_param(out, name='sia_radesys',
            datatype='char', arraysize='*', value='FK5', ucd='VOX:STC_CoordRefFrame',
            description='Coordinate system reference frame',
        )
        _vot_param(out, name='sia_equinox',
            datatype='double', value='2000.0', ucd='VOX:STC_CoordEquinox',
            description='Coordinate system equinox',
        )
        # fields
        _vot_field(out, name='raw_url', datatype='char', arraysize='*', description='URL for raw FITS image')
        _vot_field(out, name='mask_url',datatype='char', arraysize='*', description='URL for mask FITS image')
        _vot_field(out, name='jpg_url', datatype='char', arraysize='*', description='URL for JPEG image')
        _vot_field(out, name='cat_url', datatype='char', arraysize='*', description='URL for FITS table of extracted sources')        
        _vot_field(out, name='sia_mjd_obs',
            datatype='double', ucd='VOX:Image_MJDateObs',
            description='Mean Modified Julian date of the observation',
        )
        _vot_field(out, name='sia_filter',
            datatype='char', arraysize='*', ucd='VOX:BandPass_ID',
            description='Filter name',
        )
        _vot_field(out, name='filtersl',    datatype='int',    description='Filter changer slot number')
        _vot_field(out, name='ccdid',       datatype='int',    description='CCD number (0..11)')
        _vot_field(out, name='ptffield',    datatype='int',    description='PTF field number')
        _vot_field(out, name='seeing',      datatype='double', description='Seeing FWHM', unit='arcsec')
        _vot_field(out, name='airmass',     datatype='double', description='Telescope airmass')
        _vot_field(out, name='moonillf',    datatype='double', description='Moon illuminated fraction')
        _vot_field(out, name='moonesb',     datatype='double', description='Moon excess in sky brightness in V-band')
        _vot_field(out, name='photcalflag', datatype='int',    description='Flag for whether image has been photometrically calibrated (0=NO, 1=YES)')
        _vot_field(out, name='infobits',    datatype='int',    description='Info bit flags')
        _vot_field(out, name='nid',         datatype='int',    description='Night database ID')
        _vot_field(out, name='fieldid',     datatype='int',    description='Field database ID')
        _vot_field(out, name='ptfpid',      datatype='char',   description='Project name', arraysize='*')
        _vot_field(out, name='ptfprpi',     datatype='char',   description='Principal investigator', arraysize='*')

        _vot_field(out, name='moonra',   datatype='double', description='Moon J2000.0 R.A.', unit='deg', ucd='pos.eq.ra')
        _vot_field(out, name='moondec',  datatype='double', description='Moon J2000.0 Dec.', unit='deg', ucd='pos.eq.dec')
        _vot_field(out, name='moonphas', datatype='double', description='Moon phase angle',  unit='deg')
        _vot_field(out, name='moonalt',  datatype='double', description='Moon altitude')

        _vot_field(out, name='gain',    datatype='double', description='Gain of detector', unit='e-/DN')
        _vot_field(out, name='readnoi', datatype='double', description='Read noise of detector', unit='e-')
        _vot_field(out, name='darkcur', datatype='double', description='Dark current of detector at 150K', unit='e-/s')

    def write(self, row, computed_row):
        self.start_row(row, computed_row)
        for n in ('rfilename', 'afilename1', 'afilename2', 'afilename3'):
            if row[n]:
                self.write_field_v('/'.join([self.root_url, row[n]]))
            else:
                self.write_field_v('')
        # obsmjd records the observation start (docs are actually unclear here, so....??),
        # but the SIA standard wants the mean observation time.
        sia_mjd_obs = row['obsmjd'] + row['aexptime'] / (2.0*_seconds_per_day)
        self.write_field_v('%.8f' % sia_mjd_obs)
        # output remaining columns
        for c in self.columns:
            self.write_field_c(row, c)
        self.end_row()

    @staticmethod
    def get_required_cols(table):
        cols = SiaWriterBase.get_required_cols(table)
        cols.extend(table[n] for n in PtfLevel1SiaWriter.munged_column_names)
        cols.extend(table[n] for n in PtfLevel1SiaWriter.column_names)
        return cols

    def get_title(self, row):
        """Returns a title for the image corresponding to a row.
        """
        return 'PTF Level 1 Image %d' % row['pid']

    def get_url(self, row):
        """Returns a URL for the FITS image corresponding to this row.
        """
        return '/'.join([self.root_url, row['pfilename']])


class PtfLevel2SiaWriter(SiaWriterBase):
    """SIA VO table output for PTF.
    """
    munged_column_names = [
        'filename',
        'rawpsffilename',
        'psfgridfilename',
        'psfds9regfilename',
        'depthfilename',
        'uncfilename',
        'sexrfcatfilename',
        'psfrfcatfilename',
        ]
    column_names = [
        'fid',
        'rfid',
        'ppid',
        'ccdid',
        'ptffield',
        'version',
        ]

    def __init__(self, out, table, columns, server, url_root):
        super(PtfLevel2SiaWriter, self).__init__(out, table, columns, server, url_root)
        # fields
        self.columns = [table[n] for n in self.column_names]
        # parameters
        _vot_param(out, name='sia_pixflags',
            datatype='char', arraysize='*', value='F', ucd='VOX:Image_PixFlags',
            description='The image pixels were computed by resampling an existing image, and were filtered by an interpolator.',
        )
        _vot_param(out, name='sia_radesys',
            datatype='char', arraysize='*', value='FK5', ucd='VOX:STC_CoordRefFrame',
            description='Coordinate system reference frame',
        )
        _vot_param(out, name='sia_equinox',
            datatype='double', value='2000.0', ucd='VOX:STC_CoordEquinox',
            description='Coordinate system equinox',
        )
        # fields
        _vot_field(out, name='rawpsf_url',    datatype='char', description='URL for reference-image raw-PSF-file', arraysize='*')
        _vot_field(out, name='psfgrid_url',   datatype='char', description='URL for reference-image PSF-grid-file', arraysize='*')
        _vot_field(out, name='psfds9reg_url', datatype='char', description='URL for reference-image PSF-fit-catalog-DS9-region-file', arraysize='*')
        _vot_field(out, name='depth_url',     datatype='char', description='URL for reference-image depth-of-coverage image', arraysize='*')
        _vot_field(out, name='unc_url',       datatype='char', description='URL for reference-image uncertainty-image', arraysize='*')
        _vot_field(out, name='sexrfcat_url',  datatype='char', description='URL for reference-image SExtractor catalog', arraysize='*')
        _vot_field(out, name='psfrfcat_url',  datatype='char', description='URL for reference-image PSF-fit catalog', arraysize='*')
        _vot_field(out, name='sia_filter',    datatype='int',  description='Filter ID', ucd='VOX:BandPass_ID')
        _vot_field(out, name='rfid',          datatype='int',  description='Reference-image database ID')
        _vot_field(out, name='ppid',          datatype='int',  description='Reference-image-pipeline database ID')
        _vot_field(out, name='ccdid',         datatype='int',  description='CCD number (0..11)')
        _vot_field(out, name='ptffield',      datatype='int',  description='PTF field number')
        _vot_field(out, name='version',       datatype='int',  description='Reference-image database version')

    def write(self, row, computed_row):
        self.start_row(row, computed_row)
        for n in self.munged_column_names[1:]:
            self.write_field_v(self._url(row, n))
        for c in self.columns:
            self.write_field_c(row, c)
        self.end_row()

    @staticmethod
    def get_required_cols(table):
        cols = SiaWriterBase.get_required_cols(table)
        cols.extend(table[n] for n in PtfLevel2SiaWriter.munged_column_names)
        cols.extend(table[n] for n in PtfLevel2SiaWriter.column_names)
        return cols

    def get_title(self, row):
        """Returns a title for the image corresponding to a row.
        """
        return 'PTF Level 2 Image %d' % row['rfid']

    def _url(self, row, filenamecol):
        if row[filenamecol]:
            return '%s/d%d/f%d/c%d/%s' % (self.root_url, row['ptffield'], row['fid'], row['ccdid'], row[filenamecol])
        return ''

    def get_url(self, row):
        """Returns a URL for the FITS image corresponding to this row.
        """
        return self._url(row, 'filename')


_2mass_bp_ref = { 'j': 1.235, 'h': 1.662, 'k': 2.159 }
_2mass_bp_lo =  { 'j': 1.066, 'h': 1.4,   'k': 1.884 }
_2mass_bp_hi =  { 'j': 1.404, 'h': 1.924, 'k': 2.434 }


class TwomassMosaicSiaWriter(SiaWriterBase):
    """SIA VO table output for 2MASS mosaics.
    """
    column_names = [
        'cntr',
        'fname',
        'equinox',
        'filter',
        'seqnum',        
        ]

    def __init__(self, out, table, columns, server, url_root):
        super(TwomassMosaicSiaWriter, self).__init__(out, table, columns, server, url_root)
        # fields
        self.columns = [table[n] for n in self.column_names]
        # parameters
        _vot_param(out, name='sia_pixflags',
            datatype='char', arraysize='*', value='FZ', ucd='VOX:Image_PixFlags',
            description='The image pixels were computed by resampling an existing image, and were filtered by a flux-preserving interpolator.',
        )
        _vot_param(out, name='sia_radesys',
            datatype='char', arraysize='*', value='FK5', ucd='VOX:STC_CoordRefFrame',
            description='Coordinate system reference frame',
        )
        _vot_param(out, name='sia_bp_unit',
            datatype='char', arraysize='*', value='meters', ucd='VOX:BandPass_Unit',
            description='Units used to represent spectral values',
        )
        # fields
        _vot_field(out, name='sia_equinox', datatype='double', description='Coordinate system equinox', ucd='VOX:STC_CoordEquinox')
        _vot_field(out, name='sia_bp_id',   datatype='char',   description='Band pass ID', arraysize='*', ucd='VOX:BandPass_ID')
        _vot_field(out, name='sia_bp_ref',  datatype='double', description='Reference wave-length for band pass', ucd='VOX:BandPass_RefValue')
        _vot_field(out, name='sia_bp_lo',   datatype='double', description='Lower limit of the band pass', ucd='VOX:BandPass_LoLimit')
        _vot_field(out, name='sia_bp_hi',   datatype='double', description='Upper limit of the band pass', ucd='VOX:BandPass_HiLimit')
        _vot_field(out, name='seqnum',      datatype='int')

    def write(self, row, computed_row):
        self.start_row(row, computed_row)
        # output remaining columns
        self.write_field_c(row, self.columns[2])
        self.write_field_c(row, self.columns[3])
        band = row['filter'].strip()
        self.write_field_v('%.3fe-6' % _2mass_bp_ref[band])
        self.write_field_v('%.3fe-6' % _2mass_bp_lo[band])
        self.write_field_v('%.3fe-6' % _2mass_bp_hi[band])
        self.write_field_c(row, self.columns[4])
        self.end_row()

    @staticmethod
    def get_required_cols(table):
        cols = SiaWriterBase.get_required_cols(table)
        cols.extend(table[n] for n in TwomassMosaicSiaWriter.column_names)
        return cols

    def get_title(self, row):
        """Returns a title for the image corresponding to a row.
        """
        return '2MASS Mosaic %d' % row['cntr']

    def get_url(self, row):
        """Returns a URL for the FITS image corresponding to this row.
        """
        return '/'.join([self.root_url, row['fname']])


class TwomassSiaWriter(SiaWriterBase):
    """SIA VO table output for 2MASS mosaics.
    """
    column_names = [
        'filter',
        'ordate',
        'hemisphere',
        'scanno',
        'coaddno',
        'ut_date',
        'coadd_key',
        'seesh',
        'magzp',
        'msnr10',
        'fname',
    ]

    def __init__(self, out, table, columns, server, url_root):
        super(TwomassSiaWriter, self).__init__(out, table, columns, server, url_root)
        self.title_prefix = table.description.replace('Images', '') if table.description is not None else ''
        # fields
        self.columns = [table[n] for n in self.column_names]
        # parameters
        _vot_param(out, name='sia_pixflags',
            datatype='char', arraysize='*', value='CZ', ucd='VOX:Image_PixFlags',
            description='The image pixels were copied from an existing image, and contain valid flux (intensity) values.',
        )
        _vot_param(out, name='sia_radesys',
            datatype='char', arraysize='*', value='FK5', ucd='VOX:STC_CoordRefFrame',
            description='Coordinate system reference frame',
        )
        _vot_param(out, name='sia_equinox',
            datatype='double', value='2000.0', ucd='VOX:STC_CoordEquinox',
            description='Coordinate system equinox',
        )
        _vot_param(out, name='sia_bp_unit',
            datatype='char', arraysize='*', value='meters', ucd='VOX:BandPass_Unit',
            description='Units used to represent spectral values',
        )
        # fields
        _vot_field(out, name='sia_bp_id',
            datatype='char', arraysize='*', ucd='VOX:BandPass_ID',
            values=VotValues(['J', 'H', 'K']), description='Band pass ID')
        _vot_field(out, name='sia_bp_ref',
            datatype='double', ucd='VOX:BandPass_RefValue',
            description='Reference wave-length for band pass',)
        _vot_field(out, name='sia_bp_lo',
            datatype='double', ucd='VOX:BandPass_LoLimit',
            description='Lower limit of the band pass',)
        _vot_field(out, name='sia_bp_hi',
            datatype='double', ucd='VOX:BandPass_HiLimit',
            description='Upper limit of the band pass',)
        _vot_field(out, name='pers_art',
            datatype='char', arraysize='*',
            description='Persistence artifacts URL')
        _vot_field(out, name='glint_art',
            datatype='char', arraysize='*',
            description='Filter glint artifacts URL')
        _vot_field(out, name='ordate',
            datatype='char', arraysize='*',
            description='The reference date of the FITS image, in yymmdd format (yy: last 2 digits of the '
                        'observation year, mm: integer month, dd: integer day). This can differ by one day '
                        'from the actual UT observation date.')
        _vot_field(out, name='hemisphere',
            datatype='char', arraysize='*', values=VotValues(['n', 's']),
            description='The hemisphere of the 2MASS observatory where the FITS image was taken. There are '
                        'only two possible values: \'n\' = north (Mt. Hopkins), and \'s\' = south (Cerro Tololo).',)
        _vot_field(out, name='scanno', datatype='int',
            description='The nightly scan number of the FITS image')
        _vot_field(out, name='coaddno', datatype='int',
            description='The image number of the FITS image')
        _vot_field(out, name='ut_date', datatype='char', arraysize='*',
            description='UT when the FITS image was taken, in yymmdd format (yy: last 2 digits of the '
                        'observation year, mm: integer month, dd: integer day).')
        _vot_field(out, name='coadd_key', datatype='int',
            description='The coadd_key value of the FITS image. This is a unique identifier for the observation '
            'date, observatory hemisphere, nightly scan number, and image number of the FITS image. Each source '
            'in the 2MASS All-Sky Point and Extended Source Catalogs is tagged with a coadd_key value identifying '
            'the 2MASS Image Set it was extracted from.')
        _vot_field(out, name='seesh', datatype='double', unit='arcsec',
            description='Seeing Full Width Half Maximum in arcseconds.')
        _vot_field(out, name='magzp', datatype='double',
            description='Photometric zero-point magnitude of the FITS image.')
        _vot_field(out, name='magzp', datatype='msnr10',
            description='Approximate SNR=10 magnitude of the FITS image.')

    def write(self, row, computed_row):
        self.start_row(row, computed_row)
        # output remaining columns
        band = row['filter'].strip().lower()
        self.write_field_v(band.upper())
        self.write_field_v('%.3fe-6' % _2mass_bp_ref[band])
        self.write_field_v('%.3fe-6' % _2mass_bp_lo[band])
        self.write_field_v('%.3fe-6' % _2mass_bp_hi[band])
        self.write_field_v(self.get_url(row, 'pers.tbl'))
        self.write_field_v(self.get_url(row, 'glint.tbl'))
        for c in self.columns[1:-1]:
            self.write_field_c(row, c)
        self.end_row()

    @staticmethod
    def get_required_cols(table):
        cols = SiaWriterBase.get_required_cols(table)
        cols.extend(table[n] for n in TwomassSiaWriter.column_names)
        return cols

    def get_title(self, row):
        """Returns a title for the image corresponding to a row.
        """
        return '%s %s-Band Atlas Image: %s %s %03d %04d' % (
            self.title_prefix,
            row['filter'].upper(),
            row['ordate'],
            row['hemisphere'],
            row['scanno'],
            row['coaddno'],
        )

    def get_url(self, row, file=None):
        """Returns a URL for the FITS image corresponding to this row.
        """
        file = file if not file is None else 'image/' + row['fname']
        return '/'.join([self.root_url,
                         row['ordate'] + row['hemisphere'],
                         's%03d' % row['scanno'],
                         file,
                        ])

