# PaperJam Architecture

A music player for Raspberry Pi with e-ink (Waveshare) display.

## Directory Structure

```
paperjam/
├── main.py              # Application entry point, main loop
├── config.py            # Configuration, logging, version info, UI constants
├── apps/                # Application modules
│   ├── base.py          # App base class and registry
│   ├── music/           # Music player app
│   │   ├── player.py    # Main orchestrator
│   │   ├── state.py     # Player state management
│   │   ├── playlist.py  # Queue and playlist management
│   │   ├── browse.py    # Browse mode handlers
│   │   └── context_menu.py # Long-press context menus
│   ├── settings/        # Settings app
│   │   ├── app.py       # Settings orchestrator
│   │   └── categories/  # Settings category modules
│   │       ├── base.py      # Abstract base class
│   │       ├── audio.py     # Volume, output, endless playback
│   │       ├── library.py   # Library stats, rescan, recents
│   │       ├── display.py   # Colors, screensaver, language, weather
│   │       ├── network.py   # WiFi and Bluetooth management
│   │       └── system.py    # Disk, version, power mode, updates
│   ├── weather/         # Weather app
│   │   └── app.py       # Weather display
│   └── welcome/         # First-run welcome flow
│       └── app.py       # First-run setup wizard
├── core/                # Core system modules
│   ├── audio.py         # VLC audio engine wrapper
│   ├── bluetooth.py     # Bluetooth device management
│   ├── inputs.py        # Input device handling (evdev)
│   ├── library.py       # Music library scanner/manager
│   ├── metadata.py      # Audio metadata and track info
│   ├── system.py        # System operations (shutdown, display)
│   ├── battery.py       # I2C battery monitor
│   ├── settings_manager.py # Settings persistence
│   ├── weather.py       # Weather data fetching
│   └── i18n.py          # Internationalization (translations)
├── ui/                  # UI rendering
│   ├── renderer.py      # Main renderer facade
│   ├── menu.py          # Menu controller and navigation
│   ├── graphics.py      # Image processing, cover art, dithering
│   ├── overlays.py      # Status bar, battery indicator
│   ├── assets.py        # Asset loading
│   └── views/           # View components
│       ├── core.py      # Panel, Menu, Cursor classes
│       ├── items.py     # Unified Item class with rendering modes
│       ├── music_view.py    # Music browser view
│       ├── menu_view.py     # Generic menu view
│       ├── weather_view.py  # Weather display view
│       ├── popup.py         # Popup system
│       └── screensaver_view.py # Screensaver/shutdown
├── locales/             # Translation files (YAML)
│   ├── en.yaml          # English
│   ├── ko.yaml          # Korean
│   └── ja.yaml          # Japanese
└── assets/              # Fonts and static resources
```

## Core Concepts

### Application Layer

**MainApp** (`main.py`)
- Initializes all systems (audio, inputs, display)
- Routes input callbacks based on active app/view
- Manages display refresh with e-paper optimizations
- Handles system operations (shutdown, reboot, updates)

**MusicPlayerApp** (`apps/music/player.py`)
- Orchestrates music playback and browsing
- Delegates to specialized handlers:
  - `PlayerState`: UI state, playing track info
  - `PlaylistManager`: Queue management, shuffle, loop, persistence
  - `BrowseHandler`: Artists, albums, files navigation
  - `ContextMenuHandler`: Long-press actions

**SettingsApp** (`apps/settings/app.py`)
- Category-based settings with pluggable handlers
- Categories organized in `apps/settings/categories/`:
  - `AudioCategory`: Volume, output device, endless playback, Bluetooth audio
  - `LibraryCategory`: Library stats, rescanning, recents limit
  - `DisplayCategory`: Colors, screensaver, language, weather location
  - `NetworkCategory`: WiFi and Bluetooth management (wpa_supplicant)
  - `SystemCategory`: Disk usage, version, power mode, updates, restart/shutdown

### UI Architecture

**Menu Controller** (`ui/menu.py`):
- `MenuController`: Encapsulates selection state and navigation logic
- Automatically skips non-selectable items (headers, info text)
- Manages list data and cursor position
- Used by Main Menu, Settings, Context Menus, and First Run

**Panel → Menu → Item** hierarchy:
- `Panel`: Container with optional header, draws borders and shadow
- `Menu`: Manages items, cursor position, scrolling
- `Item`: Renderable elements with consistent interface

**Unified Item Class** (`ui/views/items.py`):
The `Item` class provides a unified interface for all menu items. Rendering mode
is determined by which attributes are set:
- `text`: Simple text with optional `icon` prefix
- `heading=True`: Section heading (always inverted background)
- `columns`: Two-column key/value layout (e.g., "Volume: 50%")
- `lines`: Multi-line info block with auto-wrapping
- `column_nav=True`: Horizontal navigation bar (e.g., player controls)
- `show_image=True`: Album art display with placeholder
- `show_volume=True`: Volume bar with -/+ buttons and progress
- `text_input`: Character input field with cursor

**Popup System** (`ui/views/popup.py`):
- `PopupPanel`: Overlay panel with configurable dismissal
- `PopupManager`: Manages popup stack and input routing
- Dismissal modes: INPUT (user), PROGRAMMATIC, TIMER
- Factory methods: `show_volume()`, `show_confirm()`, `show_loading()`, etc.

**Rendering Flow**:
1. App calls `renderer.render_*()` method
2. View renderer creates Panel/Menu/Items
3. Items render to PIL Image
4. Main loop applies overlays (status bar, battery)
5. PopupManager renders active popups
6. Image sent to e-paper display

### E-Paper Display Handling

**Optimization strategies**:
- Partial refresh for smooth updates
- Periodic full refresh (every 120 partials)
- Frame change detection to skip redundant refreshes
- Display sleep during screensaver

**Display modes**:
- `displayPartBaseImage()`: Full refresh with partial mode init
- `displayPartial()`: Fast partial update
- `sleep()`: Low-power mode

### Input System

Uses `evdev` for cross-device support:
- Keyboards, IR remotes, Bluetooth media buttons
- Long-press detection for context menus
- Debouncing and repeat handling

Key mappings support:
- Navigation: Arrow keys, numpad
- Media: Play/Pause, Next/Previous, Volume
- Actions: Enter, Back (with long-press variants)

### Audio System

**VLC-based** with PulseAudio/ALSA:
- Auto-detects available audio output
- Volume persistence (saved to file)
- Bluetooth audio routing

**Playback features**:
- Queue with manual additions
- Shuffle and loop modes (Off, All, One)
- Endless playback (random albums)
- Queue persistence (restores on restart)

### Library Management

**Scanning**:
- Background thread for async scanning
- Extracts metadata (artist, album, track, year)
- Caches to JSON for fast startup

**Organization**:
- Artists → Albums → Tracks hierarchy
- Favorites (tracks, albums, artists)
- Playlists (JSON files)
- Recent plays history

## Data Flow

```
User Input → InputHandler → Callbacks → App State
                                           ↓
                                      App.update()
                                           ↓
                                      App.get_frame()
                                           ↓
                                      UIRenderer
                                           ↓
                                      Overlays
                                           ↓
                                      E-Paper Display
```

## Configuration

**Config file**: `~/.config/paperjam/config.json`
- Music path, screensaver timeout, long press duration
- Invert colors, fonts, recents limit

**Data files**: `./data/`
- `library_cache.json`: Scanned library cache
- `recents.json`: Recently played tracks
- `favorites.json`: Favorite tracks/albums/artists
- `volume.json`: Persisted volume level
- `queue.json`: Persisted playback queue
- `playlists/`: User playlists

### Internationalization

**i18n Module** (`core/i18n.py`):
- YAML-based translation files in `locales/` directory
- Dot notation for nested keys: `t('player.status.playing')`
- Falls back to English if translation missing
- Supports string interpolation: `t('track.count', count=5)`

**Usage**:
```python
from core.i18n import t
label = t('player.status.playing')  # Returns "PLAYING"
```

## UI Layout Constants

All UI dimensions are defined in `config.py` to avoid magic numbers:

**Screen Layout**:
```
┌─────────────────────────────────────────────────────────┐
│ [Status Icons]                          [Battery]       │  ← Overlays
├──────────────┬──────────────────────────────────────────┤
│              │                                          │
│  Album Art   │           Main Panel                     │
│   (84x84)    │         (140 x 104)                      │
│              │                                          │
├──────────────┤                                          │
│ Status Bar   │                                          │
│   (84x12)    │                                          │
└──────────────┴──────────────────────────────────────────┘
     8px margin           Panel at x=100
```

**Key Constants** (`config.py`):
- `SCREEN_WIDTH/HEIGHT`: 250x122 (Waveshare 2.13" e-paper)
- `PANEL_X/Y/W/H`: Main content panel (100, 8, 140, 104)
- `ROW_HEIGHT`: 12px per menu row
- `COVER_SIZE_SMALL/LARGE`: Cover art dimensions (83x83, 113x113)
- `ART_PANEL_SIZE`: Album art panel (84 = cover + border)
- `SCROLLBAR_WIDTH`: 8px scrollbar track
- `UI_MARGIN`: 8px standard spacing

## Key Design Decisions

1. **PIL for rendering**: Cross-platform, easy image manipulation
2. **VLC for audio**: Robust codec support, simple API
3. **evdev for input**: Direct device access, works without X11
4. **JSON for data**: Human-readable, easy debugging
5. **Modular apps**: Clean separation, easy to add new apps
6. **View hierarchy**: Reusable UI components
7. **Panel → Menu → Item**: Consistent UI rendering pattern
8. **MenuController**: Centralized navigation logic
9. **Named constants**: All UI dimensions in config.py, no magic numbers