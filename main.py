"""
PaperJam - E-ink Music Player for Raspberry Pi.

This is the main entry point for the PaperJam application. It initializes all
subsystems and runs the main event loop.

Architecture:
    MainApp orchestrates all components:
    - SystemManager: Hardware control (display, battery, shutdown)
    - AudioEngine: VLC-based audio playback
    - InputHandler: GPIO button input processing
    - UIRenderer: E-paper display rendering
    - AppRegistry: Pluggable application management

Display Management:
    The e-paper display requires special handling:
    - Full refresh: Clears ghosting but causes visible flash
    - Partial refresh: Fast but accumulates ghosting over time
    - Solution: Track partial refresh count, force full refresh periodically
    - Sleep mode: Put display in low-power mode during screensaver

Main Loop:
    1. Check for pending input (wake display if sleeping)
    2. Route input to active popup, app, or home menu
    3. Process input via InputHandler
    4. Update current app or render home/power menu
    5. Render popups on top of frame
    6. Display frame with change detection (skip if unchanged)
    7. Run background tasks (music playback, data flush)

Usage:
    python main.py

    Or via systemd service on Raspberry Pi.
"""
from __future__ import annotations

import time
from typing import Any

from PIL import Image, ImageOps

import config as cfg
from apps.base import AppRegistry
from apps.music import MusicPlayerApp
from apps.settings import SettingsApp
from apps.weather import WeatherApp
from apps.welcome import WelcomeApp
from config import setup_logger
from core.audio import AudioEngine
from core.i18n import t
from core.inputs import InputHandler
from core.mpris import MPRISAdapter
from core.system import SystemManager
from ui.menu import MenuController
from ui.renderer import UIRenderer
from ui.views.items import Item

logger = setup_logger()

class MainApp:
    """Main application controller for PaperJam.

    Orchestrates all subsystems, manages the application lifecycle, and runs
    the main event loop. Handles navigation between apps and system operations.

    Attributes:
        sys: SystemManager for hardware control.
        audio: AudioEngine for music playback.
        inputs: InputHandler for GPIO button processing.
        renderer: UIRenderer for e-paper display output.
        registry: AppRegistry for app management.
        current_app: Currently active app, or None for home screen.
        view: Current view state ('HOME', 'APP', 'POWER').
    """

    # --- Display Refresh Configuration ---
    # E-paper displays accumulate ghosting with partial refreshes.
    # Force a full refresh after this many partial updates to clear artifacts.
    MAX_PARTIAL_REFRESHES: int = 120

    # Status icons (WiFi, Bluetooth, audio) don't change often.
    # Cache them for this many seconds to avoid repeated system calls.
    STATUS_CACHE_INTERVAL: int = 5

    def __init__(self) -> None:
        """Initialize all subsystems and apps."""
        logger.info("Initializing PaperJam...")

        # --- Core Systems ---
        self.sys = SystemManager()
        self.audio = AudioEngine()
        self.inputs = InputHandler()
        self.mpris = MPRISAdapter()
        self.renderer = UIRenderer()
        self.registry = AppRegistry()

        # --- Applications ---
        self.music_app = MusicPlayerApp(self.audio, self.inputs)
        self.settings_app = SettingsApp(self.music_app.lib, self.audio, self.inputs)
        self.weather_app = WeatherApp()

        # Link settings to music app (for endless playback, etc)
        self.music_app.set_settings(self.settings_app.settings)

        # Register apps with the registry
        self._refresh_app_names()
        self.registry.register("music", self.music_app)
        self.registry.register("weather", self.weather_app)
        self.registry.register("settings", self.settings_app)

        # Connect locale change callback
        self.settings_app.categories['DISPLAY'].set_locale_callback(self._on_locale_change)

        # --- UI State ---
        self.current_app: Any = None  # Active app instance or None
        self.view: str = 'HOME'  # HOME, APP, POWER

        # Menu Controllers
        self.home_menu = MenuController([])
        self.power_menu = MenuController([])

        # --- Display State ---
        self.first_render: bool = True  # Force full refresh on first frame
        self._last_frame_bytes: bytes | None = None  # For change detection
        self._partial_refresh_count: int = 0  # Partials since last full refresh
        self._max_partial_refreshes: int = self.MAX_PARTIAL_REFRESHES
        self._display_sleeping: bool = False  # True when in low-power mode

        # --- Status Icon Cache ---
        # Avoid checking WiFi/Bluetooth/audio status every frame
        self._status_cache: tuple[Any, Any, Any] = (None, None, None)
        self._status_cache_time: float = 0
        self._status_cache_interval: int = self.STATUS_CACHE_INTERVAL

        # --- Setup Global Callbacks ---
        self.sys.on_shutdown_request = self._handle_shutdown_request
        self.settings_app.categories['SYSTEM'].set_screen_clear_callback(
            self._perform_screen_clear_shutdown
        )
        self.settings_app.categories['SYSTEM'].set_update_callback(self._perform_update)
        self.settings_app.categories['SYSTEM'].set_reset_callback(self._perform_reset)

        # Music app needs display access for screensaver
        self.music_app.set_display_callback(lambda img: self._display(img))

        # Volume callbacks (global - work from any screen)
        self.music_app.set_volume_callbacks(self._vol_up, self._vol_down)

        # --- Initial Setup ---
        self._refresh_home_menu()
        self.inputs.set_callbacks(self._get_home_callbacks())

        # Welcome app for first-run setup
        self.welcome_app = WelcomeApp(self.music_app.lib, self.inputs)
        self.welcome_app.set_shutdown_callback(self._welcome_shutdown)
        self.welcome_app.set_display_callback(lambda img: self._display(img))

        # --- First Run Handling ---
        if self.music_app.lib.is_first_run():
            self._run_first_startup()
        else:
            # Check for auto-update on startup (only if not first run)
            self._check_auto_update()
            # Check if version requires library rescan
            self._check_needs_rescan()

        # --- MPRIS for Bluetooth Media Controls ---
        self.mpris.set_callbacks(self._get_mpris_callbacks())
        self.mpris.start()

    def _refresh_app_names(self) -> None:
        """Refresh app display names with current locale translations."""
        self.music_app.name = t('menu.music')
        self.weather_app.name = t('menu.weather')
        self.settings_app.name = t('menu.settings')

    def _on_locale_change(self, new_locale: str) -> None:
        """Handle locale change - refresh all localized text.

        Args:
            new_locale: New locale code (e.g., 'en', 'ko', 'ja').
        """
        self._refresh_app_names()
        self._refresh_home_menu()
        self.settings_app.on_locale_change()

    def _refresh_home_menu(self) -> None:
        """Rebuild home menu items with current locale."""
        items: list[Item] = []

        # Add registered apps
        for app_id, name in self.registry.get_app_names():
            items.append(Item(text=name, id=app_id))

        # Add power option at the end
        items.append(Item(text=t('menu.power'), id='POWER'))

        self.home_menu.set_items(items, reset_index=False)

    def _run_first_startup(self):
        """Handle first run using WelcomeApp."""
        logger.info("First run detected")

        self.welcome_app.on_enter()
        self.inputs.set_callbacks(self.welcome_app.get_callbacks())

        while self.welcome_app.running:
            if not self.inputs.check_inputs():
                break

            self.welcome_app.update()

            # Update callbacks if view changed
            self.inputs.set_callbacks(self.welcome_app.get_callbacks())

            frame = self.welcome_app.get_frame()
            self._display(frame, full_refresh=self.first_render)
            self.first_render = False
            time.sleep(0.05)

        self.first_render = True
        logger.info("Welcome app completed")

    def _welcome_shutdown(self):
        """Handle shutdown request from welcome app."""
        logger.info("User chose to shutdown for library setup")
        frame, _ = self.renderer.render_menu("SETUP", [
            Item(lines=[
                t('welcome.shutdown_loading'),
                "",
                t('welcome.add_music_prompt'),
                f"{str(cfg.MUSIC_PATH)}"
            ], selectable=False)
        ], -1, 0)
        self._display(frame, full_refresh=True)
        time.sleep(2)
        self.sys.shutdown()

    def _check_needs_rescan(self):
        """Check if version requires library rescan."""
        if not cfg.NEEDS_RESCAN:
            return

        logger.info("Version requires library rescan")

        # Show rescan message
        frame, _ = self.renderer.render_menu(t('settings.system.check_updates'), [Item(text=t('welcome.scanning_library'), selectable=False)], -1, 0)
        self._display(frame, full_refresh=True)

        # Trigger async rescan
        self.music_app.lib.scan_async(force=True)

    def _check_auto_update(self):
        """Check for updates on startup if auto-update is enabled."""
        if not self.settings_app.settings.get('auto_update', False):
            return

        logger.info("Auto-update enabled, checking for updates...")

        # Show checking status
        frame, _ = self.renderer.render_menu(t('settings.system.auto_update'), [Item(text=t('updates.checking'), selectable=False)], -1, 0)
        self._display(frame, full_refresh=True)

        # Check for updates
        has_updates, msg = self.sys.check_for_updates()

        if has_updates:
            logger.info("Updates available, installing...")
            frame, _ = self.renderer.render_menu(t('settings.system.auto_update'), [Item(text=t('updates.installing'), selectable=False)], -1, 0)
            self._display(frame, full_refresh=True)

            success, result_msg = self.sys.perform_update()
            if not success:
                logger.error(f"Auto-update failed: {result_msg}")
                frame, _ = self.renderer.render_menu(t('settings.system.auto_update'), [Item(text=t('updates.failed', msg=result_msg[:18]), selectable=False)], -1, 0)
                self._display(frame, full_refresh=True)
                time.sleep(2)
            # If successful, perform_update will restart the app
        else:
            logger.info(f"Auto-update check: {msg}")

    def run(self) -> None:
        """Main event loop.

        Runs until interrupted or an unrecoverable error occurs.
        Handles input routing, app updates, rendering, and display output.
        """
        logger.info("Entering main loop")
        try:
            while True:
                # --- Input Handling ---
                # Wake display from sleep if user pressed a button
                if self._display_sleeping and self.inputs.has_pending_input():
                    self._wake_display()

                # Route input to the appropriate handler:
                # 1. Active popup (e.g., volume overlay) takes priority
                # 2. Current app if one is running
                # 3. Power menu if showing
                # 4. Home menu otherwise
                popup_callbacks = self.renderer.get_popup_callbacks()
                if popup_callbacks:
                    # Volume callbacks always available even during popups
                    popup_callbacks['vol_up'] = self._vol_up
                    popup_callbacks['vol_down'] = self._vol_down
                    self.inputs.set_callbacks(popup_callbacks)
                elif self.current_app:
                    self.inputs.set_callbacks(self.current_app.get_callbacks())
                elif self.view == 'POWER':
                    self.inputs.set_callbacks(self._get_power_callbacks())
                else:
                    self.inputs.set_callbacks(self._get_home_callbacks())

                # Process pending inputs (returns False on shutdown signal)
                if not self.inputs.check_inputs():
                    break

                # Check battery level (may trigger shutdown)
                self.sys.check_battery()

                # --- Frame Rendering ---
                frame: Image.Image | None = None
                force_full: bool = False

                if self.current_app:
                    # Update the active app
                    is_running = False
                    try:
                        is_running = self.current_app.update()
                    except Exception as e:
                        logger.exception(f"App Update Error: {e}")

                    # Check if app requested a full refresh (e.g., view change)
                    if hasattr(self.current_app, 'state'):
                        if getattr(self.current_app.state, 'needs_refresh', False):
                            force_full = True
                            self.current_app.state.needs_refresh = False

                    if not is_running:
                        self.close_app()
                    else:
                        frame = self.current_app.get_frame()
                else:
                    # Render home or power menu
                    if self.view == 'HOME':
                        frame, scroll = self.renderer.render_menu(
                            t('menu.home'),
                            **self.home_menu.get_render_args()
                        )
                        self.home_menu.scroll_offset = scroll
                    elif self.view == 'POWER':
                        frame = self._render_power_menu()

                # --- Display Output ---
                if frame:
                    # Render any active popups on top of the frame
                    frame = self.renderer.render_with_popups(frame)

                    # Force full refresh if a popup just expired (clears artifacts)
                    if self.renderer.popup_needs_refresh():
                        force_full = True

                    self._display(frame, force_full)

                    # Put display to sleep during screensaver to save power
                    if (self.current_app == self.music_app and
                        self.music_app.state.screensaver_image is not None and
                        not self._display_sleeping):
                        self._sleep_display()

                # --- Background Tasks ---
                # Keep music playing even when in settings
                if self.current_app != self.music_app:
                    self.music_app.update()

                # Periodically flush favorites to disk (lazy persistence)
                self.music_app.lib.flush_favs()

                # Target ~20 FPS (50ms per frame)
                time.sleep(0.05)

        except KeyboardInterrupt:
            logger.info("Keyboard Interrupt")
        except Exception as e:
            logger.critical(f"Critical Error: {e}", exc_info=True)
        finally:
            # Ensure data is saved on exit
            self.music_app.lib.flush_all()
            self.sys.sleep_display()

    def launch_app(self, app_id: str) -> None:
        """Launch an app by its registry ID.

        Args:
            app_id: App identifier (e.g., 'music', 'settings').
        """
        app = self.registry.get_app(app_id)
        if app:
            logger.info(f"Launching app: {app_id}")
            self.current_app = app
            self.inputs.set_callbacks(app.get_callbacks())
            if hasattr(app, 'on_enter'):
                app.on_enter()
            if hasattr(app, 'refresh_list'):
                app.refresh_list()
            self.first_render = True  # Force full refresh on app launch

    def close_app(self) -> None:
        """Close the current app and return to home screen."""
        if self.current_app:
            if hasattr(self.current_app, 'on_exit'):
                self.current_app.on_exit()
        self.current_app = None
        self.view = 'HOME'
        self.inputs.set_callbacks(self._get_home_callbacks())
        self.first_render = True  # Force full refresh on return to home

    def _wake_display(self) -> None:
        """Wake display from low-power sleep mode.

        Called when user input is detected while the display is sleeping
        (e.g., during screensaver).
        """
        if self._display_sleeping:
            self.sys.wake_display()
            self._display_sleeping = False
            self.first_render = True  # Force full refresh to clear any artifacts
            logger.debug("Display awakened from sleep")

    def _sleep_display(self) -> None:
        """Put display into low-power sleep mode.

        Called when screensaver activates. Reduces power consumption
        significantly on the Pi Zero.
        """
        if not self._display_sleeping:
            self.sys.sleep_display()
            self._display_sleeping = True
            logger.debug("Display entering sleep mode")

    def _vol_up(self):
        self.settings_app.categories['AUDIO'].set_volume(5)
        vol = self.settings_app.categories['AUDIO'].volume_level
        self._show_volume_popup(vol)

    def _vol_down(self):
        self.settings_app.categories['AUDIO'].set_volume(-5)
        vol = self.settings_app.categories['AUDIO'].volume_level
        self._show_volume_popup(vol)

    def _get_mpris_callbacks(self):
        """Get callbacks for MPRIS (Bluetooth media controls)."""
        return {
            'play_pause': self.music_app.toggle_play,
            'next': self.music_app.next_track,
            'prev': self.music_app.prev_track,
            'vol_up': self._vol_up,
            'vol_down': self._vol_down
        }

    def _show_volume_popup(self, level):
        """Show or update volume popup."""
        # Check if there's already a volume popup
        popup = self.renderer.popups.peek()
        title = t('general.volume_popup')
        if popup and hasattr(popup, 'state') and popup.state and popup.state.extra.get('is_volume'):
            # Update existing popup
            popup.update(extra={'level': level, 'title': title, 'is_volume': True})
        else:
            # Create new volume popup
            popup = self.renderer.popups.show_volume(title, level)
            popup.state.extra['is_volume'] = True

    # --- Home Menu Interaction ---
    def _get_home_callbacks(self):
        return {
            'up': lambda: self.home_menu.move_selection(-1),
            'down': lambda: self.home_menu.move_selection(1),
            'enter': self._handle_home_selection,
            'vol_up': self._vol_up,
            'vol_down': self._vol_down
        }

    def _handle_home_selection(self):
        item = self.home_menu.get_selected_item()
        if not item: return

        item_id = item.id

        if item_id == "POWER":
            self._show_power_menu()
        else:
            self.launch_app(item_id)

    # --- Power Menu ---
    def _show_power_menu(self):
        self.view = 'POWER'
        items = [
            Item(text=t('menu.reboot'), id='REBOOT'),
            Item(text=t('menu.shutdown'), id='SHUTDOWN')
        ]
        self.power_menu.set_items(items)
        self.inputs.set_callbacks(self._get_power_callbacks())

    def _get_power_callbacks(self):
        return {
            'up': lambda: self.power_menu.move_selection(-1),
            'down': lambda: self.power_menu.move_selection(1),
            'enter': self._handle_power_selection,
            'back': self._close_power_menu,
            'vol_up': self._vol_up,
            'vol_down': self._vol_down
        }

    def _render_power_menu(self):
        frame, scroll = self.renderer.render_menu(
            t('menu.power'),
            **self.power_menu.get_render_args()
        )
        self.power_menu.scroll_offset = scroll
        return frame

    def _handle_power_selection(self):
        item = self.power_menu.get_selected_item()
        if not item:
            return
        if item.id == 'REBOOT':
            self._perform_system_action(t('system_messages.rebooting'), self.sys.reboot)
        elif item.id == 'SHUTDOWN':
            self._perform_shutdown()

    def _close_power_menu(self):
        self.view = 'HOME'
        self.inputs.set_callbacks(self._get_home_callbacks())

    def _perform_shutdown(self):
        """Perform shutdown with random cover art display."""
        # Save volume before shutdown
        self.settings_app.categories['AUDIO'].save_volume()

        # Get random cover art from library
        cover = self.music_app.lib.get_random_cover()
        frame = self.renderer.render_shutdown(cover)
        self._display(frame, full_refresh=True, skip_battery=True, skip_status=True)
        time.sleep(1)
        self.sys.shutdown()

    def _perform_system_action(self, msg, action):
        # Save volume before system action (reboot)
        self.settings_app.categories['AUDIO'].save_volume()

        from ui.views.items import Item
        frame, _ = self.renderer.render_menu(t('settings.categories.system'), [Item(text=msg, selectable=False)], 0, 0)
        self._display(frame, full_refresh=True)
        time.sleep(2)
        action()

    def _handle_shutdown_request(self, reason="User Request"):
        logger.info(f"Shutdown requested: {reason}")
        if reason == "LOW BATTERY":
            frame, _ = self.renderer.render_menu(t('system_messages.low_battery'), [Item(text=t('system_messages.shutting_down'), selectable=False)], 0, 0)
            self._display(frame, full_refresh=True, skip_battery=False)
            time.sleep(2)
        self._perform_shutdown()

    def _perform_screen_clear_shutdown(self):
        logger.info("Clearing screen for shutdown")
        self.sys.clear_display()
        self.sys.shutdown()

    def _perform_update(self):
        """Check for and perform updates."""
        logger.info("Checking for updates")

        # Show checking status
        frame, _ = self.renderer.render_menu(t('settings.system.check_updates'), [Item(text=t('updates.checking'), selectable=False)], -1, 0)
        self._display(frame, full_refresh=True)

        # Check for updates
        has_updates, msg = self.sys.check_for_updates()

        if has_updates:
            frame, _ = self.renderer.render_menu(t('settings.system.check_updates'), [Item(text=t('updates.updating'), selectable=False)], -1, 0)
            self._display(frame, full_refresh=True)

            success, result_msg = self.sys.perform_update()
            if not success:
                frame, _ = self.renderer.render_menu(t('settings.system.check_updates'), [Item(text=t('general.error_prefix', msg=result_msg), selectable=False)], -1, 0)
                self._display(frame, full_refresh=True)
                time.sleep(2)
        else:
            frame, _ = self.renderer.render_menu(t('settings.system.check_updates'), [Item(text=msg, selectable=False)], -1, 0)
            self._display(frame, full_refresh=True)
            time.sleep(1.5)

    def _perform_reset(self):
        """Reset all data files and reboot."""
        logger.info("Resetting data and rebooting")

        # Show resetting status
        frame, _ = self.renderer.render_menu(t('system_messages.reset'), [Item(text=t('system_messages.resetting'), selectable=False)], -1, 0)
        self._display(frame, full_refresh=True)

        # Delete data files
        try:
            import shutil
            import json
            if cfg.DATA_DIR.exists():
                shutil.rmtree(cfg.DATA_DIR)
            if cfg.CONFIG_FILE.exists():
                cfg.CONFIG_FILE.unlink()

            # Create default config file
            cfg.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(cfg.CONFIG_FILE, 'w') as f:
                json.dump(cfg.DEFAULT_CONFIG, f, indent=4)
            logger.info("Created default config file")
        except OSError as e:
            logger.error(f"Reset error: {e}")

        # Reboot
        time.sleep(1)
        self.sys.reboot()

    # --- Display Output ---
    def _display(
        self,
        img: Image.Image,
        full_refresh: bool = False,
        skip_battery: bool = False,
        skip_status: bool = False
    ) -> None:
        """Send a frame to the e-paper display.

        Handles overlay rendering, color inversion, change detection, and
        the partial/full refresh strategy for optimal e-paper performance.

        Args:
            img: PIL Image to display (1-bit or grayscale).
            full_refresh: Force a full refresh (clears ghosting).
            skip_battery: Don't render battery indicator.
            skip_status: Don't render status icons (WiFi, Bluetooth, audio).

        Display Refresh Strategy:
            E-paper displays have two refresh modes:
            - Full refresh: Complete screen clear + redraw. Slow (~1s) but removes
              all ghosting artifacts. Causes visible flash.
            - Partial refresh: Fast (~0.3s) update of changed pixels only. Leaves
              slight ghosting that accumulates over time.

            We use partial refresh for speed but periodically force a full refresh
            (every MAX_PARTIAL_REFRESHES frames) to clear accumulated ghosting.

        Change Detection:
            Compares frame bytes to avoid redundant display updates when nothing
            changed. This saves power and reduces display wear.
        """
        # --- Apply Overlays ---
        if not skip_status:
            # Cache status checks to avoid expensive system calls every frame
            now = time.time()
            if now - self._status_cache_time > self._status_cache_interval:
                self._status_cache = (
                    self.sys.check_audio_device(),
                    self.sys.check_wifi(),
                    self.sys.check_bluetooth()
                )
                self._status_cache_time = now
            img = self.renderer.overlays.draw_status_icons(img, *self._status_cache)

        if not skip_battery:
            img = self.renderer.overlays.draw_battery(img)

        # Apply color inversion if enabled in settings
        if self.settings_app.invert_colors:
            img = ImageOps.invert(img.convert('L')).convert('1')

        # Rotate for 180° mounted display (do BEFORE change detection)
        img = img.rotate(180)

        # --- Change Detection ---
        # Skip display update if frame hasn't changed (saves power)
        img_bytes = img.tobytes()
        if not full_refresh and not self.first_render and img_bytes == self._last_frame_bytes:
            return
        self._last_frame_bytes = img_bytes

        # --- Determine Refresh Type ---
        # Force full refresh periodically to clear ghosting artifacts
        needs_periodic_full = self._partial_refresh_count >= self._max_partial_refreshes

        # --- Send to Display ---
        epd = self.sys.get_display()
        if epd:
            try:
                buffer = epd.getbuffer(img)
                if self.first_render or full_refresh or needs_periodic_full:
                    # Full refresh: reinitialize display and clear
                    epd.init()
                    epd.displayPartBaseImage(buffer)
                    self.first_render = False
                    self._partial_refresh_count = 0
                else:
                    # Partial refresh: fast update
                    epd.displayPartial(buffer)
                    self._partial_refresh_count += 1
            except Exception as e:
                logger.error(f"Display Error: {e}")

if __name__ == "__main__":
    app = MainApp()
    app.launch_app("music")  # Start directly in Music app
    app.run()