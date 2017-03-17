import os

def configure(conf):
    if conf.options.gsoap_dir:
        if not conf.options.gsoap_incdir:
            conf.options.gsoap_incdir=conf.options.gsoap_dir + "/include"
        if not conf.options.gsoap_libdir:
            conf.options.gsoap_libdir=conf.options.gsoap_dir + "/lib"

    if conf.options.gsoap_incdir:
        gsoap_incdir=[conf.options.gsoap_incdir]
    else:
        gsoap_incdir=[]

    if conf.options.gsoap_libdir:
        gsoap_libdir=[conf.options.gsoap_libdir]
    else:
        gsoap_libdir=[]

    if conf.options.gsoap_libs:
        gsoap_libs=conf.options.gsoap_libs.split()
    else:
        gsoap_libs=['gsoap++']


    fragment='''#include <stdsoap2.h>

void soap_serializeheader(struct soap*){return;}

int soap_getfault(struct soap*){return 0;}
int soap_putfault(struct soap*){return 0;}
int soap_getheader(struct soap*){return 0;}
int soap_putheader(struct soap*){return 0;}

const char** soap_faultstring(struct soap*){return 0;}

void soap_serializefault(struct soap*){return;}

struct Namespace namespaces[10];
const char* soap_check_faultdetail(struct soap*){return 0;}
const char** soap_faultdetail(struct soap*){return 0;}
const char** soap_faultsubcode(struct soap*){return 0;}
const char** soap_faultcode(struct soap*){return 0;}
const char* soap_check_faultsubcode(struct soap*){return 0;}

extern "C"{
int soap_getelement(struct soap*){return 0;}
int soap_markelement(struct soap*){return 0;}
int soap_putelement(struct soap*){return 0;}
}

int main(int argc, char **argv) {
	(void)argc; (void)argv;
	return 0;
}
'''
    conf.check_cxx(msg="Checking for gSoap",
                   fragment=fragment,
                   header_name='stdsoap2.h',
                   includes=gsoap_incdir,
                   uselib_store='gsoap',
                   libpath=gsoap_libdir,
                   rpath=gsoap_libdir,
                   lib=gsoap_libs)

def options(opt):
    gsoap=opt.add_option_group('gsoap Options')
    gsoap.add_option('--gsoap-dir',
                     help='Base directory where gsoap is installed')
    gsoap.add_option('--gsoap-incdir',
                     help='Directory where gsoap include files are installed')
    gsoap.add_option('--gsoap-libdir',
                     help='Directory where gsoap library files are installed')
    gsoap.add_option('--gsoap-libs',
                     help='Names of the midc libraries without prefix or suffix\n'
                     '(e.g. "gsoap")')
