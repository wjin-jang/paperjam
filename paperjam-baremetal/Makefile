# PaperJam Bare-Metal OS Makefile
# Target: Raspberry Pi Zero 2 W (BCM2710, ARM Cortex-A53)

# Cross-compiler toolchain
# Use aarch64-none-elf- if you have ARM's bare-metal toolchain
# Use aarch64-linux-gnu- if using the Linux cross-compiler from apt
CROSS ?= aarch64-linux-gnu-
CC = $(CROSS)gcc
AS = $(CROSS)gcc
LD = $(CROSS)ld
OBJCOPY = $(CROSS)objcopy
OBJDUMP = $(CROSS)objdump

# Directories
SRC_DIR = src
BUILD_DIR = build
BOOT_DIR = boot
LIB_DIR = lib

# Output
TARGET = kernel8
KERNEL = $(BOOT_DIR)/$(TARGET).img

# Compiler flags
CFLAGS = -Wall -Wextra -O2 -ffreestanding -nostdlib -nostartfiles
CFLAGS += -mcpu=cortex-a53 -march=armv8-a
CFLAGS += -I$(SRC_DIR) -I$(LIB_DIR)
CFLAGS += -DRPI_ZERO2W
CFLAGS += -fno-builtin -fno-stack-protector
CFLAGS += -mgeneral-regs-only

# Assembler flags
ASFLAGS = -mcpu=cortex-a53 -march=armv8-a

# Linker flags
LDFLAGS = -nostdlib -T linker.ld

# Source files
ASM_SOURCES = $(SRC_DIR)/boot/start.S \
              $(SRC_DIR)/boot/exceptions.S

C_SOURCES = $(SRC_DIR)/main.c \
            $(SRC_DIR)/hal/gpio.c \
            $(SRC_DIR)/hal/timer.c \
            $(SRC_DIR)/hal/uart.c \
            $(SRC_DIR)/hal/spi.c \
            $(SRC_DIR)/hal/i2c.c \
            $(SRC_DIR)/hal/pwm.c \
            $(SRC_DIR)/hal/irq.c \
            $(SRC_DIR)/hal/mmc.c \
            $(SRC_DIR)/sys/heap.c \
            $(SRC_DIR)/sys/scheduler.c \
            $(SRC_DIR)/sys/power.c \
            $(SRC_DIR)/drivers/epd_2in13_v4.c \
            $(SRC_DIR)/drivers/pisugar3.c \
            $(SRC_DIR)/drivers/buttons.c \
            $(SRC_DIR)/drivers/audio.c \
            $(SRC_DIR)/fs/diskio.c \
            $(SRC_DIR)/audio/playback.c \
            $(SRC_DIR)/audio/mp3_decoder.c \
            $(SRC_DIR)/audio/flac_decoder.c \
            $(SRC_DIR)/audio/wav_decoder.c \
            $(SRC_DIR)/audio/id3.c \
            $(SRC_DIR)/audio/flac_meta.c \
            $(SRC_DIR)/gfx/framebuffer.c \
            $(SRC_DIR)/gfx/fonts.c \
            $(SRC_DIR)/gfx/dither.c \
            $(SRC_DIR)/gfx/text.c \
            $(SRC_DIR)/gfx/jpeg.c \
            $(SRC_DIR)/gfx/icons.c \
            $(SRC_DIR)/ui/menu.c \
            $(SRC_DIR)/ui/music_view.c \
            $(SRC_DIR)/ui/screensaver.c \
            $(SRC_DIR)/ui/renderer.c \
            $(SRC_DIR)/ui/volume_overlay.c \
            $(SRC_DIR)/ui/browse_view.c \
            $(SRC_DIR)/ui/context_menu.c \
            $(SRC_DIR)/ui/settings_view.c \
            $(SRC_DIR)/app/player.c \
            $(SRC_DIR)/app/library.c \
            $(SRC_DIR)/app/playlist.c \
            $(SRC_DIR)/app/favorites.c \
            $(SRC_DIR)/app/settings.c

# FatFS sources
FATFS_SOURCES = $(LIB_DIR)/fatfs/ff.c \
                $(LIB_DIR)/fatfs/ffunicode.c

# Object files
ASM_OBJECTS = $(patsubst $(SRC_DIR)/%.S,$(BUILD_DIR)/%.o,$(ASM_SOURCES))
C_OBJECTS = $(patsubst $(SRC_DIR)/%.c,$(BUILD_DIR)/%.o,$(C_SOURCES))
FATFS_OBJECTS = $(patsubst $(LIB_DIR)/%.c,$(BUILD_DIR)/lib/%.o,$(FATFS_SOURCES))

OBJECTS = $(ASM_OBJECTS) $(C_OBJECTS) $(FATFS_OBJECTS)

# Default target
all: dirs $(KERNEL)

# Create build directories
dirs:
	@mkdir -p $(BUILD_DIR)/boot
	@mkdir -p $(BUILD_DIR)/hal
	@mkdir -p $(BUILD_DIR)/sys
	@mkdir -p $(BUILD_DIR)/drivers
	@mkdir -p $(BUILD_DIR)/fs
	@mkdir -p $(BUILD_DIR)/audio
	@mkdir -p $(BUILD_DIR)/gfx
	@mkdir -p $(BUILD_DIR)/ui
	@mkdir -p $(BUILD_DIR)/app
	@mkdir -p $(BUILD_DIR)/lib/fatfs
	@mkdir -p $(BOOT_DIR)

# Link kernel
$(BUILD_DIR)/$(TARGET).elf: $(OBJECTS)
	$(LD) $(LDFLAGS) -o $@ $^

# Create binary image
$(KERNEL): $(BUILD_DIR)/$(TARGET).elf
	$(OBJCOPY) -O binary $< $@
	@echo "Built $(KERNEL) - $$(stat -c %s $@ 2>/dev/null || stat -f %z $@) bytes"

# Compile assembly
$(BUILD_DIR)/%.o: $(SRC_DIR)/%.S
	@mkdir -p $(dir $@)
	$(AS) $(ASFLAGS) -c $< -o $@

# Compile C sources
$(BUILD_DIR)/%.o: $(SRC_DIR)/%.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@

# Compile FatFS
$(BUILD_DIR)/lib/%.o: $(LIB_DIR)/%.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@

# Disassembly
disasm: $(BUILD_DIR)/$(TARGET).elf
	$(OBJDUMP) -d $< > $(BUILD_DIR)/$(TARGET).dis

# Clean
clean:
	rm -rf $(BUILD_DIR)
	rm -f $(KERNEL)

# Deploy to SD card (Linux)
deploy: $(KERNEL)
	@if [ -d "/media/$(USER)/boot" ]; then \
		cp $(BOOT_DIR)/* /media/$(USER)/boot/; \
		sync; \
		echo "Deployed to SD card"; \
	else \
		echo "SD card not mounted at /media/$(USER)/boot"; \
	fi

.PHONY: all dirs clean disasm deploy
