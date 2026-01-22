################################################################################
#
# paperjam
#
################################################################################

PAPERJAM_VERSION = 1.0.0
PAPERJAM_SITE = $(BR2_EXTERNAL_PAPERJAM_PATH)/../
PAPERJAM_SITE_METHOD = local
PAPERJAM_LICENSE = MIT
PAPERJAM_LICENSE_FILES = LICENSE

PAPERJAM_DEPENDENCIES = \
	python3 \
	python-pillow \
	python-pyyaml \
	python-mutagen \
	python-dbus \
	python-evdev \
	python-libgpiod \
	vlc \
	waveshare-epd

define PAPERJAM_INSTALL_TARGET_CMDS
	# Create application directory
	mkdir -p $(TARGET_DIR)/home/paperjam/app

	# Copy application files
	cp -r $(@D)/main.py $(TARGET_DIR)/home/paperjam/app/
	cp -r $(@D)/config.py $(TARGET_DIR)/home/paperjam/app/

	# Copy Python packages
	cp -r $(@D)/core $(TARGET_DIR)/home/paperjam/app/
	cp -r $(@D)/ui $(TARGET_DIR)/home/paperjam/app/
	cp -r $(@D)/apps $(TARGET_DIR)/home/paperjam/app/

	# Copy assets and locales
	cp -r $(@D)/assets $(TARGET_DIR)/home/paperjam/app/
	cp -r $(@D)/locales $(TARGET_DIR)/home/paperjam/app/

	# Create data directory
	mkdir -p $(TARGET_DIR)/home/paperjam/app/data
	mkdir -p $(TARGET_DIR)/home/paperjam/app/data/playlists

	# Copy data files if they exist
	if [ -d $(@D)/data ]; then \
		cp -r $(@D)/data/* $(TARGET_DIR)/home/paperjam/app/data/ 2>/dev/null || true; \
	fi

	# Create config directory
	mkdir -p $(TARGET_DIR)/home/paperjam/.config/paperjam
	mkdir -p $(TARGET_DIR)/home/paperjam/.cache/paperjam

	# Set permissions
	chmod +x $(TARGET_DIR)/home/paperjam/app/main.py
endef

define PAPERJAM_USERS
	paperjam -1 paperjam -1 * /home/paperjam /bin/sh audio,video,input,spi,i2c,gpio,bluetooth,pulse-access PaperJam User
endef

$(eval $(generic-package))
