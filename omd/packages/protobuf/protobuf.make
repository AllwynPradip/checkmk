# This package builds the python protobuf module and also protoc (for tests)
PROTOBUF := protobuf
PROTOBUF_VERS := 3.20.1
PROTOBUF_DIR := $(PROTOBUF)-$(PROTOBUF_VERS)
# Increase this to enforce a recreation of the build cache
PROTOBUF_BUILD_ID := 7
# The cached package contains the python major/minor version, so include this in the cache name in order to trigger
# a rebuild on a python version change.
PROTOBUF_BUILD_ID := $(PROTOBUF_BUILD_ID)-python$(PYTHON_MAJOR_DOT_MINOR)

PROTOBUF_PATCHING := $(BUILD_HELPER_DIR)/$(PROTOBUF_DIR)-patching
PROTOBUF_CONFIGURE := $(BUILD_HELPER_DIR)/$(PROTOBUF_DIR)-configure
PROTOBUF_UNPACK := $(BUILD_HELPER_DIR)/$(PROTOBUF_DIR)-unpack
PROTOBUF_BUILD := $(BUILD_HELPER_DIR)/$(PROTOBUF_DIR)-build
PROTOBUF_BUILD_PYTHON := $(BUILD_HELPER_DIR)/$(PROTOBUF_DIR)-build-python
PROTOBUF_BUILD_LIBRARY := $(BUILD_HELPER_DIR)/$(PROTOBUF_DIR)-build-library
PROTOBUF_INTERMEDIATE_INSTALL := $(BUILD_HELPER_DIR)/$(PROTOBUF_DIR)-install-intermediate
PROTOBUF_INTERMEDIATE_INSTALL_PYTHON := $(BUILD_HELPER_DIR)/$(PROTOBUF_DIR)-install-intermediate-python
PROTOBUF_INTERMEDIATE_INSTALL_LIBRARY := $(BUILD_HELPER_DIR)/$(PROTOBUF_DIR)-install-intermediate-library
PROTOBUF_CACHE_PKG_PROCESS := $(BUILD_HELPER_DIR)/$(PROTOBUF_DIR)-cache-pkg-process
PROTOBUF_CACHE_PKG_PROCESS_PYTHON := $(BUILD_HELPER_DIR)/$(PROTOBUF_DIR)-cache-pkg-process-python
PROTOBUF_CACHE_PKG_PROCESS_LIBRARY := $(BUILD_HELPER_DIR)/$(PROTOBUF_DIR)-cache-pkg-process-library
PROTOBUF_INSTALL := $(BUILD_HELPER_DIR)/$(PROTOBUF_DIR)-install
PROTOBUF_INSTALL_PYTHON := $(BUILD_HELPER_DIR)/$(PROTOBUF_DIR)-install-python
PROTOBUF_INSTALL_LIBRARY := $(BUILD_HELPER_DIR)/$(PROTOBUF_DIR)-install-library

PROTOBUF_INSTALL_DIR_PYTHON := $(INTERMEDIATE_INSTALL_BASE)/$(PROTOBUF_DIR)-python
PROTOBUF_INSTALL_DIR_LIBRARY := $(INTERMEDIATE_INSTALL_BASE)/$(PROTOBUF_DIR)-library
PROTOBUF_BUILD_DIR := $(PACKAGE_BUILD_DIR)/$(PROTOBUF_DIR)
#PROTOBUF_WORK_DIR := $(PACKAGE_WORK_DIR)/$(PROTOBUF_DIR)

# Used by other OMD packages
PACKAGE_PROTOBUF_DESTDIR         := $(PROTOBUF_INSTALL_DIR_LIBRARY)
PACKAGE_PROTOBUF_LDFLAGS         := -L$(PACKAGE_PROTOBUF_DESTDIR)/lib
PACKAGE_PROTOBUF_LD_LIBRARY_PATH := $(PACKAGE_PROTOBUF_DESTDIR)/lib
PACKAGE_PROTOBUF_INCLUDE_PATH    := $(PACKAGE_PROTOBUF_DESTDIR)/include/google/protobuf
PACKAGE_PROTOBUF_PROTOC_BIN      := $(PACKAGE_PROTOBUF_DESTDIR)/bin/protoc

SITE_PACKAGES_PATH_REL := "lib/python$(PYTHON_VERSION_MAJOR).$(PYTHON_VERSION_MINOR)/site-packages/"

$(PROTOBUF)-build-library: $(BUILD_HELPER_DIR) $(PROTOBUF_CACHE_PKG_PROCESS_LIBRARY)

# We have a globally defined $(PROTOBUF_UNPACK) target, but we need some special
# handling here, because downloaded archive name does not match the omd package name
$(PROTOBUF_UNPACK): $(PACKAGE_DIR)/$(PROTOBUF)/protobuf-python-$(PROTOBUF_VERS).tar.gz
	$(RM) -r $(PROTOBUF_BUILD_DIR)
	$(MKDIR) $(PACKAGE_BUILD_DIR)
	$(TAR_GZ) $< -C $(PACKAGE_BUILD_DIR)
	$(MKDIR) $(BUILD_HELPER_DIR)
	$(TOUCH) $@

# NOTE: We can probably remove the CXXFLAGS hack below when we use a more recent
# protobuf version. Currently -Wall is enabled for builds with GCC, and newer
# GCC versions complain.
$(PROTOBUF_CONFIGURE): $(PROTOBUF_PATCHING)
	cd $(PROTOBUF_BUILD_DIR) && \
	    export LD_LIBRARY_PATH="$(PACKAGE_PYTHON_LD_LIBRARY_PATH)" && \
	    CXXFLAGS="-Wno-stringop-overflow" ./configure --prefix=""
	$(TOUCH) $@

$(PROTOBUF_BUILD_LIBRARY): $(INTERMEDIATE_INSTALL_BAZEL)

$(PROTOBUF_BUILD_PYTHON): $(PROTOBUF_BUILD_LIBRARY) $(INTERMEDIATE_INSTALL_BAZEL)
	cd $(PROTOBUF_BUILD_DIR)/python && \
	    export LD_LIBRARY_PATH="$(PACKAGE_PYTHON_LD_LIBRARY_PATH)" && \
	    echo "$(PYTHON3_MODULES_INSTALL_DIR)/$(SITE_PACKAGES_PATH_REL)" > "$(PYTHON_INSTALL_DIR)/$(SITE_PACKAGES_PATH_REL)python_modules.pth" && \
	    $(PACKAGE_PYTHON_EXECUTABLE) setup.py build --cpp_implementation
	$(TOUCH) $@

$(PROTOBUF_BUILD): $(PROTOBUF_BUILD_LIBRARY) $(PROTOBUF_BUILD_PYTHON)
	file $(PROTOBUF_BUILD_DIR)/src/protoc | grep ELF >/dev/null
	ldd $(PROTOBUF_BUILD_DIR)/src/protoc | grep -v libstdc++ >/dev/null
	$(TOUCH) $@

$(PROTOBUF_CACHE_PKG_PROCESS): $(PROTOBUF_CACHE_PKG_PROCESS_PYTHON) $(PROTOBUF_CACHE_PKG_PROCESS_LIBRARY)

PROTOBUF_CACHE_PKG_PATH_PYTHON := $(call cache_pkg_path,$(PROTOBUF_DIR)-python,$(PROTOBUF_BUILD_ID))

$(PROTOBUF_CACHE_PKG_PATH_PYTHON):
	$(call pack_pkg_archive,$@,$(PROTOBUF_DIR)-python,$(PROTOBUF_BUILD_ID),$(PROTOBUF_INTERMEDIATE_INSTALL_PYTHON))

$(PROTOBUF_CACHE_PKG_PROCESS_PYTHON): $(PROTOBUF_CACHE_PKG_PATH_PYTHON)
	$(call unpack_pkg_archive,$(PROTOBUF_CACHE_PKG_PATH_PYTHON),$(PROTOBUF_DIR)-python)
	$(call upload_pkg_archive,$(PROTOBUF_CACHE_PKG_PATH_PYTHON),$(PROTOBUF_DIR)-python,$(PROTOBUF_BUILD_ID))
	$(TOUCH) $@

PROTOBUF_CACHE_PKG_PATH_LIBRARY := $(call cache_pkg_path,$(PROTOBUF_DIR)-library,$(PROTOBUF_BUILD_ID))

$(PROTOBUF_CACHE_PKG_PATH_LIBRARY):
	$(call pack_pkg_archive,$@,$(PROTOBUF_DIR)-library,$(PROTOBUF_BUILD_ID),$(PROTOBUF_INTERMEDIATE_INSTALL_LIBRARY))

$(PROTOBUF_CACHE_PKG_PROCESS_LIBRARY): $(PROTOBUF_CACHE_PKG_PATH_LIBRARY)
	$(call unpack_pkg_archive,$(PROTOBUF_CACHE_PKG_PATH_LIBRARY),$(PROTOBUF_DIR)-library)
	$(call upload_pkg_archive,$(PROTOBUF_CACHE_PKG_PATH_LIBRARY),$(PROTOBUF_DIR)-library,$(PROTOBUF_BUILD_ID))
	$(TOUCH) $@

$(PROTOBUF_INTERMEDIATE_INSTALL): $(PROTOBUF_INTERMEDIATE_INSTALL_PYTHON) $(PROTOBUF_INTERMEDIATE_INSTALL_LIBRARY)

$(PROTOBUF_INTERMEDIATE_INSTALL_LIBRARY): $(PROTOBUF_BUILD_LIBRARY)
	file $(PROTOBUF_BUILD_DIR)/src/protoc | grep ELF >/dev/null
	ldd $(PROTOBUF_BUILD_DIR)/src/protoc | grep -v libstdc++ >/dev/null
	make -C $(PROTOBUF_BUILD_DIR) DESTDIR=$(PROTOBUF_INSTALL_DIR_LIBRARY) install
	$(TOUCH) $@

$(PROTOBUF_INTERMEDIATE_INSTALL_PYTHON): $(PROTOBUF_BUILD_PYTHON) $(INTERMEDIATE_INSTALL_BAZEL)

	# With Python 3.12, distutils is removed and we need to use setuptools from our python modules.
	# By adding the pth file, we make the modules available for our own python interpreter.
	cd $(PROTOBUF_BUILD_DIR)/python && \
	    export LD_LIBRARY_PATH="$(PACKAGE_PYTHON_LD_LIBRARY_PATH)" && \
	    echo "$(PYTHON3_MODULES_INSTALL_DIR)/$(SITE_PACKAGES_PATH_REL)" > "$(PYTHON_INSTALL_DIR)/$(SITE_PACKAGES_PATH_REL)python_modules.pth" && \
	    $(PACKAGE_PYTHON_EXECUTABLE) setup.py install \
	    --cpp_implementation \
	    --root=$(PROTOBUF_INSTALL_DIR_PYTHON) \
	    --prefix=''
	# Quick hack to unblock CMK-18157
	patchelf --set-rpath "\$$ORIGIN/../../../../.." \
	    $(PROTOBUF_INSTALL_DIR_PYTHON)/lib/python$(PYTHON_MAJOR_DOT_MINOR)/site-packages/google/protobuf/pyext/_message.cpython-$(PYTHON_MAJOR_MINOR)-x86_64-linux-gnu.so
	$(TOUCH) $@

$(PROTOBUF_INSTALL): $(PROTOBUF_INSTALL_LIBRARY) $(PROTOBUF_INSTALL_PYTHON)

$(PROTOBUF_INSTALL_LIBRARY): $(PROTOBUF_CACHE_PKG_PROCESS_LIBRARY)
# Only install the libraries we really need in run time environment. The
# PROTOBUF_INTERMEDIATE_INSTALL_LIBRARY step above installs the libprotobuf.a
# for building the cmc. However, this is not needed later in runtime environment.
# Also the libprotobuf-lite and libprotoc are not needed. We would normally exclude
# the files from being added to the intermediate package, but since we have the
# requirement for cmc and also want to use the build cache for that step, we need
# to do the filtering here. See CMK-9913.
	$(RSYNC) \
	    --exclude 'libprotobuf.a' \
	    --exclude 'libprotoc*' \
	    --exclude 'libprotobuf-lite.*' \
	    --exclude 'protobuf-lite.pc' \
	    $(PROTOBUF_INSTALL_DIR_LIBRARY)/ $(DESTDIR)$(OMD_ROOT)/
	$(TOUCH) $@


$(PROTOBUF_INSTALL_PYTHON): $(PROTOBUF_CACHE_PKG_PROCESS_PYTHON)
	$(RSYNC) $(PROTOBUF_INSTALL_DIR_PYTHON)/ $(DESTDIR)$(OMD_ROOT)/
	$(TOUCH) $@
