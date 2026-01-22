################################################################################
#
# waveshare-epd
#
################################################################################

WAVESHARE_EPD_VERSION = master
WAVESHARE_EPD_SITE = https://github.com/waveshare/e-Paper.git
WAVESHARE_EPD_SITE_METHOD = git
WAVESHARE_EPD_LICENSE = MIT
WAVESHARE_EPD_LICENSE_FILES = LICENSE

WAVESHARE_EPD_DEPENDENCIES = \
	python3 \
	python-pillow \
	python-spidev \
	python-libgpiod

define WAVESHARE_EPD_INSTALL_TARGET_CMDS
	# Create destination directory
	mkdir -p $(TARGET_DIR)/usr/lib/python$(PYTHON3_VERSION_MAJOR)/site-packages/waveshare_epd

	# Copy Python library
	cp -r $(@D)/RaspberryPi_JetsonNano/python/lib/waveshare_epd/*.py \
		$(TARGET_DIR)/usr/lib/python$(PYTHON3_VERSION_MAJOR)/site-packages/waveshare_epd/

	# Create __init__.py if missing
	touch $(TARGET_DIR)/usr/lib/python$(PYTHON3_VERSION_MAJOR)/site-packages/waveshare_epd/__init__.py
endef

$(eval $(generic-package))
