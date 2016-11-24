.SUFFIXES:
SHELL = /bin/sh
INSTALL = install
INSTALL_PROGRAM = $(INSTALL) -m 755 -p
INSTALL_DATA = $(INSTALL) -m 644 -p
INSTALL_DIR = $(INSTALL) -m 755 -d

CM_IBE_DIR = $(shell cd ../..; pwd)

# ================================================================
# Targets
# ================================================================

all :           build

.PHONY :        all build clean install
.DELETE_ON_ERROR : ;

# Cleans the build tree
clean :
	rm -rf build/

distclean : clean
	rm -rf dist/ ibe.egg_info/ Paste*

build :
	. $(CM_IBE_DIR)/env/bin/activate; python setup.py build

install :
	. $(CM_IBE_DIR)/env/bin/activate; python setup.py install

# ================================================================

