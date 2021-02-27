CM_IBE_DIR = $(shell cd ..; pwd)
TGTDIR = $(CM_IBE_DIR)/env
CC = gcc
CFLAGS = -O3
export CC
export CFLAGS

all: compile

$(TGTDIR):
	cd $(CM_IBE_DIR); virtualenv --system-site-packages env

compile: $(TGTDIR) compile-cfitsio compile-wcslib compile-sqlalchemy
compile-cfitsio: setup-cfitsio
	make -C cfitsio-3.3310/
compile-wcslib: setup-wcslib
	make -C wcslib-4.14/
compile-sqlalchemy: setup-sqlalchemy
	source $(TGTDIR)/bin/activate; cd SQLAlchemy-0.8.3; python setup.py build

install: $(TGTDIR) install-cfitsio install-wcslib install-sqlalchemy
install-cfitsio: compile-cfitsio
	make -C cfitsio-3.3310/ all shared fpack funpack install
	mkdir -p $(TGTDIR)/bin
	cp cfitsio-3.3310/fpack $(TGTDIR)/bin/
	cp cfitsio-3.3310/funpack $(TGTDIR)/bin/
install-wcslib: compile-wcslib
	make -C wcslib-4.14/ install
	rm $(TGTDIR)/include/wcslib
	ln -s $(TGTDIR)/include/wcslib-4.14 $(TGTDIR)/include/wcslib
install-sqlalchemy: compile-sqlalchemy
	source $(TGTDIR)/bin/activate; cd SQLAlchemy-0.8.3; python setup.py install

clean: clean-cfitsio clean-wcslib clean-sqlalchemy
clean-cfitsio:
	rm -rf cfitsio-3.3310/
clean-wcslib:
	rm -rf wcslib-4.14/
clean-sqlalchemy:
	rm -rf SQLAlchemy-0.8.3/

setup-cfitsio:
	if [ ! -d cfitsio-3.3310/ ] ; then \
		tar -xf dist/cfitsio3310.tar.gz ; \
		mv cfitsio/ cfitsio-3.3310/ ; cd cfitsio-3.3310/ ; \
		./configure --prefix=$(TGTDIR) --enable-ssse3 ; \
	else true ; \
	fi

setup-wcslib:
	if [ ! -d wcslib-4.14/ ] ; then \
		tar -xf dist/wcslib-4.14.tar.bz2 ; \
		cd wcslib-4.14 ; \
		./configure --prefix=$(TGTDIR) --with-cfitsiolib=$(TGTDIR)/lib --with-cfitsioinc=$(TGTDIR)/include ; \
	else true ; \
	fi

setup-sqlalchemy:
	if [ ! -d SQLAlchemy-0.8.3/ ] ; then \
		tar -xf dist/SQLAlchemy-0.8.3.tar.gz ; \
		patch -p0 < dist/SQLAlchemy-0.8.3.patch ; \
	else true ; \
	fi
