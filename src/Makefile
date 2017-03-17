.SUFFIXES:
SHELL = /bin/sh
INSTALL = install
INSTALL_PROGRAM = $(INSTALL) -m 755 -p
INSTALL_DATA = $(INSTALL) -m 644 -p
INSTALL_DIR = $(INSTALL) -m 755 -d

# The directory for the base product group,
# of which this product is a member
CM_IBE_DIR = $(shell cd ../..; pwd)

# Standard directory variables
prefix=$(CM_IBE_DIR)
exec_prefix=$(prefix)
cgibindir=$(exec_prefix)/web/cgi-bin
srcdir=.

# The names of all executables
progs = nph-serve

# The source files
common = Access.cpp Cgi.cpp Cutout.cpp Sqlite.cpp
sources = $(common) $(addsuffix .cpp, $(progs))

# ================================================================
# Setup / sanity checks
# ================================================================

# Determine whether or not compilation can occur
comp_tgts = all install test $(progs) $(sources:.cpp=.o) $(sources:.cpp=.d)
dep_check = true
ifeq ($(filter-out $(MAKECMDGOALS), $(comp_tgts)), $(strip $(comp_tgts)))
    ifneq ($(MAKECMDGOALS),)
        dep_check = false
    endif
endif

# Function to search PATH for a file
pathsearch = $(firstword $(wildcard $(addsuffix /$(strip $(1)),$(subst :, ,$(PATH)))))

# Standard compiler variables
CXX = g++
CXXFLAGS = -O2 -Wall
CPPFLAGS = -I$(srcdir) \
           -I$(CM_ENV_DIR)/core/include \
           -I$(CM_IBE_DIR)/env/include \
           -I$(CM_BASE_DIR)/include \
           -DIBE_DATA_ROOT='"$(CM_IBE_DIR)/web/html/data"'

# When compiling, create/update build environment file
ifeq ($(dep_check),true)
    build_env = $(call pathsearch, $(CXX)) $(CM_IBE_DIR) $(CXXFLAGS)
    prev_env =  $(shell cat ./.build_env)
    ifneq ($(strip $(build_env)), $(strip $(prev_env)))
        $(warning creating/updating build environment file (.build_env))
        $(shell rm -f ./.build_env)
        $(shell echo "$(build_env)" > ./.build_env)
    endif
endif

# ================================================================
# External library dependencies
# ================================================================

libs = -Wl,--rpath=$(CM_ENV_DIR)/core/lib \
       -Wl,--rpath=$(CM_IBE_DIR)/env/lib \
       -L$(CM_ENV_DIR)/core/lib -lboost_filesystem -lboost_regex -lboost_system \
       -L$(CM_BASE_DIR)/lib -lssoclient \
       -lgsoap -lsqlite3 \
       -L$(CM_IBE_DIR)/env/lib -lcfitsio -lwcs \
       -lm

# ================================================================
# Pattern Rules
# ================================================================

vpath %.cpp	$(srcdir)
vpath %.h	$(srcdir)

# Creates object files from C++ source files
%.o : %.cpp
		$(CXX) -c $(CPPFLAGS) $(CXXFLAGS) $< -o $@

# Creates dependency files from C++ source files
%.d : %.cpp
		@echo ... Creating $@; set -e; rm -f $@; \
		$(CXX) -MM -MF $@ $(CPPFLAGS) $<; \
		sed 's,\($*\)\.o[ :]*,\1.o $@ : ./.build_env ,g' < $@ > $@.$$$$; \
		mv $@.$$$$ $@ 

# ================================================================
# Targets
# ================================================================

all :		$(progs)

.PHONY :	all clean distclean installdirs install installdocs test uninstall
.SECONDARY :	$(sources:.cpp=.d)
.DELETE_ON_ERROR : ;

ifeq ($(dep_check),true)
    include $(sources:.cpp=.d)
endif

# Compiles executables
nph-serve:	nph-serve.o $(common:.cpp=.o)
		$(CXX) $(CXXFLAGS) -o $@ $^ $(libs)

# Cleans the build tree
clean :
		rm -f *.o *.d $(progs) ./.build_env core

# The same as clean
distclean : 	clean

# Creates required installation directories
installdirs :
		$(INSTALL_DIR) $(cgibindir)

# Installs libraries and header files 
install :	$(progs) installdirs
		$(INSTALL_PROGRAM) $(progs) $(cgibindir)

# Uninstalls the product
uninstall :
		rm -f $(addprefix $(cgibindir)/, $(progs))

# ================================================================

