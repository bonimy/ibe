
CM_IBE_DIR = $(shell cd ..; pwd)
TGTDIR     = $(CM_IBE_DIR)/env

all:	c++ python dirs

$(TGTDIR):	
	make -C ../deps/ install

c++:	$(TGTDIR)
	make -C c++/

python:	$(TGTDIR)
	make -C python/

dirs:	
	@( mkdir $(CM_IBE_DIR)/logs 2>/dev/null; echo "" >/dev/null )

clean:	
	make -C c++/ clean
	make -C python/ clean

install:	$(TGTDIR)
	make -C c++/ install
	make -C python/ install

distclean:	
	make -C c++/ distclean
	make -C python/ distclean
	rm -rf $(CM_IBE_DIR)/env

# vi: tabstop=16 shiftwidth=16 noexpandtab syntax=make :

