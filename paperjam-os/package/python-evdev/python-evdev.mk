################################################################################
#
# python-evdev
#
################################################################################

PYTHON_EVDEV_VERSION = 1.6.1
PYTHON_EVDEV_SOURCE = evdev-$(PYTHON_EVDEV_VERSION).tar.gz
PYTHON_EVDEV_SITE = https://files.pythonhosted.org/packages/source/e/evdev
PYTHON_EVDEV_SETUP_TYPE = setuptools
PYTHON_EVDEV_LICENSE = BSD-3-Clause
PYTHON_EVDEV_LICENSE_FILES = LICENSE

# Build-time dependencies
PYTHON_EVDEV_DEPENDENCIES = host-python-setuptools

# Need to set kernel headers path for cross-compilation
PYTHON_EVDEV_ENV = \
	PYTHON_EVDEV_KERNEL_HEADERS=$(STAGING_DIR)/usr/include

$(eval $(python-package))
