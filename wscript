import os

def options(opt):
    opt.load(['compiler_c','compiler_cxx','gnu_dirs','ipac','irsa',
              'pqxx','cfitsio','boost','wcs','gsoap'])

def configure(conf):
    conf.load(['compiler_c','compiler_cxx','gnu_dirs','ipac','irsa',
               'pqxx','cfitsio','boost','wcs','gsoap'])
    conf.check_boost(lib='filesystem system regex')
    
def build(bld):
    default_flags=['-Wall', '-Wextra', '-O2']
    default_flags.append('-DIBE_DATA_ROOT="' + bld.env.IRSA_DIR + '/web/html/ibe/data"')

    bld.program(source=['src/Access.cpp',
                        'src/Cgi.cpp',
                        'src/Cutout.cpp',
                        'src/nph-serve.cpp'],
                target='nph-ibe_data',
                cxxflags=default_flags,
                use=['BOOST','ipac','irsa_sso','pqxx','cfitsio','wcs','gsoap'],
                install_path=bld.env.WEB_CGI_DIR + '/ibe'
    )

    bld.install_files(bld.env.HTML_DIR + '/ibe',bld.path.ant_glob("html/**"),
                      cwd=bld.path.find_dir('html'), relative_trick=True);

    data_dir = bld.env.HTML_DIR + '/ibe/data/'
    bld.symlink_as(data_dir + 'twomass/sixxcat/sixxcat',
                   '/stage/tmass-data/links/sixxcatalog')
    bld.symlink_as(data_dir + 'twomass/calibration/calibration',
                   '/stage/tmass-data/links/calibration')
    bld.symlink_as(data_dir + 'twomass/allsky/allsky',
                   '/stage/tmass-data/links/allsky')
    bld.symlink_as(data_dir + 'twomass/full/full',
                   '/stage/tmass-data/links/full')
    bld.symlink_as(data_dir + 'twomass/sixxfull/sixxfull',
                   '/stage/tmass-data/links/sixxfull')
    bld.symlink_as(data_dir + 'twomass/mosaic/sixdeg',
                   '/stage/irsa-data-2mass-mosaic/links/mosaic/sixdeg')
    bld.symlink_as(data_dir + 'wise/neowiser/p1bm_frm',
                   '/stage/irsa-wise-links-public/links-neowiser/l1b')
    bld.symlink_as(data_dir + 'wise/prelim_postcryo/p1bm_frm',
                   '/stage/irsa-wise-links-public/links-prelim-postcryo/l1b-2band')
    bld.symlink_as(data_dir + 'wise/cryo_3band/3band_p3am_cdd',
                   '/stage/irsa-wise-links-public/links-3band/l3a-3band')
    bld.symlink_as(data_dir + 'wise/cryo_3band/3band_p1bm_frm',
                   '/stage/irsa-wise-links-public/links-3band/l1b-3band')
    bld.symlink_as(data_dir + 'wise/postcryo/2band_p1bm_frm',
                   '/stage/irsa-wise-links-public/links-postcryo/l1b-2band')
    bld.symlink_as(data_dir + 'wise/prelim/p1bm_frm',
                   '/stage/irsa-wise-links-public/links-prelim/l1b')
    bld.symlink_as(data_dir + 'wise/prelim/p3am_cdd',
                   '/stage/irsa-wise-links-public/links-prelim/l3a')
    bld.symlink_as(data_dir + 'wise/allsky/4band_p3am_cdd',
                   '/stage/irsa-wise-links-public/links-allsky/l3a-4band')
    bld.symlink_as(data_dir + 'wise/allsky/4band_p1bm_frm',
                   '/stage/irsa-wise-links-public/links-allsky/l1b-4band')
    bld.symlink_as(data_dir + 'wise/allwise/p3am_cdd',
                   '/stage/irsa-wise-links-public/links-allwise/l3a')
    bld.symlink_as(data_dir + 'wise/merge/merge_p1bm_frm',
                   '/stage/irsa-wise-links-public/links-merge/l1b')
    bld.symlink_as(data_dir + 'wise/merge/merge_p3am_cdd',
                   '/stage/irsa-wise-links-public/links-merge/l3a')
    bld.symlink_as(data_dir + 'ptf/images/level1',
                   '/stage/irsa-ptf-links/')
    bld.symlink_as(data_dir + 'ptf/images/level2',
                   '/stage/irsa-ptf-links/refims-links')
    bld.symlink_as(data_dir + 'ztf/products/raw',
                   '/stage/irsa-ztf-links/ingest-test/raw')
    bld.symlink_as(data_dir + 'ztf/products/cal',
                   '/stage/irsa-ztf-links/ingest-test/cal')
    bld.symlink_as(data_dir + 'ztf/products/sci',
                   '/stage/irsa-ztf-links/ingest-test/sci')

    bld.symlink_as(data_dir + 'spitzer/seip_science/images',
                   '/irsadata/SPITZER/Enhanced/SEIP/images')
    bld.symlink_as(data_dir + 'spitzer/seip_ancillary/images',
                   '/irsadata/SPITZER/Enhanced/SEIP/images')
