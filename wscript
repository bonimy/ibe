import os

def options(opt):
    opt.load(['compiler_c','compiler_cxx','gnu_dirs','ipac','irsa',
              'sqlite','cfitsio','boost','wcs','gsoap'])

def configure(conf):
    conf.load(['compiler_c','compiler_cxx','gnu_dirs','ipac','irsa',
               'sqlite','cfitsio','boost','wcs','gsoap'])
    conf.check_boost(lib='filesystem system regex')
    
def build(bld):
    default_flags=['-Wall', '-Wextra', '-O2']
    default_flags.append('-DIBE_DATA_ROOT="' + bld.env.IRSA_DIR + '/web/html/ibe/data"')

    bld.program(source=['src/Access.cpp',
                        'src/Cgi.cpp',
                        'src/Cutout.cpp',
                        'src/Sqlite.cpp',
                        'src/nph-serve.cpp'],
                target='nph-ibe_data',
                cxxflags=default_flags,
                use=['BOOST','ipac','irsa_sso','sqlite','cfitsio','wcs','gsoap'],
                install_path=bld.env.WEB_CGI_DIR + '/ibe'
    )

    bld.install_files(bld.env.HTML_DIR + '/ibe',bld.path.ant_glob("html/**"),
                      cwd=bld.path.find_dir('html'), relative_trick=True);
