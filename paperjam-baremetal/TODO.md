# PaperJam Bare-Metal OS - TODO

## Status Legend
- [ ] Not started
- [x] Complete
- [~] In progress / Partial

---

## Phase 1: Boot and Core HAL
- [x] Linker script (load at 0x80000)
- [x] start.S (stack setup, BSS clear, exception vectors)
- [x] EL2 to EL1 transition
- [x] GPIO driver
- [x] Timer driver (microsecond ticks, delays)
- [x] UART driver (debugging)
- [x] Heap allocator

## Phase 2: Peripheral Drivers
- [x] SPI driver (master mode)
- [x] I2C driver (BSC1)
- [x] E-paper driver (init, partial/full refresh, sleep/wake)
- [x] PiSugar driver (battery %, charging status)
- [x] Button driver (polling, debounce, long press)
- [x] PWM audio driver

## Phase 3: Filesystem
- [x] SD/MMC card driver
- [x] FatFS integration
- [x] diskio.c implementation
- [ ] Proper error handling for filesystem operations
- [ ] File caching for frequently accessed metadata

## Phase 4: Audio Subsystem
- [x] PWM audio output
- [x] Ring buffer playback
- [x] Decoder interface
- [x] WAV decoder (functional)
- [~] FLAC decoder (stub - needs dr_flac integration)
- [~] MP3 decoder (stub - needs libmad integration)
- [x] ID3 tag parser (v1, v2.3, v2.4)
- [x] FLAC metadata parser (Vorbis comments)
- [ ] Gapless playback
- [ ] ReplayGain support
- [ ] M4A/AAC support (complex, low priority)

## Phase 5: Graphics Layer
- [x] 1-bit framebuffer (250x122)
- [x] Pixel operations (set, get, rect, line)
- [x] Bitmap font (8x8 ASCII)
- [x] Text rendering with alignment
- [x] Text ellipsis for long strings
- [x] Bayer dithering (4x4, 8x8)
- [x] Floyd-Steinberg dithering
- [x] 16x16 icon set
- [~] JPEG decoder (minimal baseline implementation)
- [ ] Larger font sizes (12pt, 16pt)
- [ ] CJK font support
- [ ] Album art display in now playing view
- [ ] Animated transitions (fade, slide)

## Phase 6: UI System
- [x] Menu controller
- [x] Menu item rendering
- [x] Music view (now playing)
- [x] Browse view (folder navigation)
- [x] Screensaver view
- [x] Context menus
- [x] Volume overlay
- [x] Settings view
- [ ] Queue view (list with current track highlight)
- [ ] Search/filter functionality
- [ ] Album art view
- [ ] Playlist management UI
- [ ] Confirmation dialogs
- [ ] Toast notifications

## Phase 7: Application Logic
- [x] Library scanner
- [x] Metadata extraction
- [x] Queue management
- [x] Favorites system
- [x] Settings persistence
- [x] Player state machine
- [x] Shuffle mode
- [x] Repeat modes (none, all, one)
- [ ] Library cache (binary format for fast load)
- [ ] Album/artist grouping
- [ ] Smart playlists
- [ ] Recently played tracking
- [ ] Play count statistics
- [ ] Resume playback on boot

## Phase 8: Power and Integration
- [x] Cooperative scheduler
- [x] WFI for power saving
- [x] Display sleep mode
- [x] Low battery warning
- [x] Low battery shutdown
- [ ] Activity-based screensaver timeout
- [ ] Deep sleep mode
- [ ] Wake on button press from deep sleep

---

## Known Issues

### High Priority
- [ ] MP3 decoder is stub only - needs libmad integration
- [ ] FLAC decoder is stub only - needs dr_flac integration
- [ ] Album art not displayed in now playing view
- [ ] Queue view not fully implemented

### Medium Priority
- [ ] Long filenames may be truncated incorrectly
- [ ] Unicode characters not supported in UI
- [ ] No error recovery if SD card is removed
- [ ] Partial refresh can leave artifacts after many updates

### Low Priority
- [ ] No timezone support for file timestamps
- [ ] Settings view could use icons
- [ ] Volume bar could be graphical instead of numeric

---

## Future Enhancements

### Audio
- [ ] Equalizer (bass/treble adjustment)
- [ ] Crossfade between tracks
- [ ] Sleep timer
- [ ] Alarm/wake function

### Display
- [ ] Multiple theme support (inverted, high contrast)
- [ ] Configurable screensaver styles
- [ ] Progress bar styles (line, dots, blocks)
- [ ] Custom font loading from SD card

### Connectivity (Would require significant work)
- [ ] USB mass storage mode
- [ ] USB audio output
- [ ] Bluetooth audio (requires firmware stack)
- [ ] WiFi streaming (requires full network stack)

### User Experience
- [ ] First-run setup wizard
- [ ] Button mapping configuration
- [ ] Gesture support (button combinations)
- [ ] Accessibility features (larger UI elements)

---

## Technical Debt

### Code Quality
- [ ] Add more inline documentation
- [ ] Consistent error handling patterns
- [ ] Unit tests (where feasible for bare-metal)
- [ ] Static analysis cleanup

### Performance
- [ ] Profile audio decoding performance
- [ ] Optimize display refresh regions
- [ ] Reduce memory fragmentation in heap
- [ ] DMA for audio output (instead of IRQ-based)

### Build System
- [ ] Separate debug/release configurations
- [ ] Automatic dependency generation
- [ ] Version numbering from git tags
- [ ] Build size optimization (-Os vs -O2)

---

## Hardware Variants

### Planned Support
- [ ] Raspberry Pi Zero W (original)
- [ ] Raspberry Pi 3B/3B+
- [ ] Different e-paper sizes (2.9", 4.2")
- [ ] Different battery modules

### Display Options
- [ ] Waveshare 2.9" (296x128)
- [ ] Waveshare 4.2" (400x300)
- [ ] Good Display alternatives

---

## Documentation

- [x] README.md
- [x] INSTALL.md
- [x] TODO.md
- [ ] Hardware wiring diagram (Fritzing/KiCad)
- [ ] API documentation
- [ ] Architecture overview document
- [ ] Contributing guidelines

---

## Version Roadmap

### v1.0 (Current Target)
- Basic playback (WAV working, MP3/FLAC stubs)
- Core UI (now playing, browse, settings)
- Essential features (favorites, queue, volume)

### v1.1
- Full MP3 support (libmad integration)
- Full FLAC support (dr_flac integration)
- Album art display
- Queue view improvements

### v1.2
- Library caching for fast startup
- Resume playback on boot
- Improved metadata handling
- CJK font support

### v2.0
- Multiple display support
- Advanced audio features (EQ, crossfade)
- USB connectivity
- Playlist import/export
