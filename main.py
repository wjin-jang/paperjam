"""
PaperJam - E-ink Music Player for Raspberry Pi

Main application entry point. Handles:
- System initialization (audio, display, inputs)
- Application lifecycle (music player, settings, welcome)
- Main event loop with display refresh optimization
- Global callbacks (volume, shutdown, battery monitoring)

E-paper display considerations:
- Periodic full refresh prevents ghosting (every 30 partials)
- Frame change detection skips redundant refreshes
- Display sleeps during screensaver to save power
- Wake on user input with full refresh
"""
import time
import sys
import traceback
from PIL import Image

import config as cfg
import version
from core.audio import AudioEngine
from core.inputs import InputHandler
from core.system import SystemManager
from core.logger import setup_logger
from core.app_registry import AppRegistry
from ui.renderer import UIRenderer

from apps.music import MusicPlayerApp
from apps.settings import SettingsApp
from apps.welcome import WelcomeApp

logger = setup_logger()

class MainApp:
    def __init__(self):
        logger.info("Initializing PaperJam...")
        
        # Core Systems
        self.sys = SystemManager()
        self.audio = AudioEngine()
        self.inputs = InputHandler()
        self.renderer = UIRenderer()
        self.registry = AppRegistry()

        # Apps
        self.music_app = MusicPlayerApp(self.audio, self.inputs)
        # Give settings app access to library
        self.settings_app = SettingsApp(self.music_app.lib, self.audio, self.inputs)
        
        # Link settings to music app (for endless playback, etc)
        self.music_app.set_settings(self.settings_app.settings)
        
        # Register Apps
        self.music_app.name = "Music Player"
        self.settings_app.name = "System Settings"
        self.registry.register("music", self.music_app)
        self.registry.register("settings", self.settings_app)

        # UI State
        self.current_app = None
        self.view = 'HOME' # HOME, APP, CONFIRM
        self.menu_idx = 0
        self.confirm_target = None
        self.confirm_idx = 0
        
        # Display State
        self.first_render = True
        self._last_frame_hash = None  # For change detection
        self._partial_refresh_count = 0  # Track partial refreshes for periodic full refresh
        self._max_partial_refreshes = 120  # Max partials before forced full refresh
        self._display_sleeping = False  # Track display sleep state for screensaver

        # Setup Global Callbacks
        self.sys.on_shutdown_request = self._handle_shutdown_request
        self.settings_app.categories['SYSTEM'].set_screen_clear_callback(self._perform_screen_clear_shutdown)
        self.settings_app.categories['SYSTEM'].set_update_callback(self._perform_update)
        self.settings_app.categories['SYSTEM'].set_reset_callback(self._perform_reset)

        # Music App Display Callback
        self.music_app.set_display_callback(lambda img: self._display(img))
        
        # Volume Callbacks (Global)
        self.music_app.set_volume_callbacks(self._vol_up, self._vol_down)

        # Initial Input Setup
        self.inputs.set_callbacks(self._get_home_callbacks())

        # Welcome App (for first run)
        self.welcome_app = WelcomeApp(self.music_app.lib, self.inputs)
        self.welcome_app.set_shutdown_callback(self._welcome_shutdown)
        self.welcome_app.set_display_callback(lambda img: self._display(img))

        # First Run
        if self.music_app.lib.is_first_run():
            self._run_first_startup()
        else:
            # Check for auto-update on startup (only if not first run)
            self._check_auto_update()
            # Check if version requires library rescan
            self._check_needs_rescan()

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
        frame = self.renderer.render_menu("SETUP", [
            {"type": "info", "lines": [
                "Shutting down...",
                "",
                "Add music to:",
                f"{str(cfg.MUSIC_PATH)[:22]}"
            ]}
        ], -1, 0, info_indices=[0])
        self._display(frame, full_refresh=True)
        time.sleep(2)
        self.sys.shutdown()

    def _check_needs_rescan(self):
        """Check if version requires library rescan."""
        if not version.NEEDS_RESCAN:
            return

        logger.info("Version requires library rescan")

        # Show rescan message
        frame = self.renderer.render_menu("UPDATE", ["Rescanning library..."], -1, 0)
        self._display(frame, full_refresh=True)

        # Trigger async rescan
        self.music_app.lib.scan_async(force=True)

    def _check_auto_update(self):
        """Check for updates on startup if auto-update is enabled."""
        if not self.settings_app.settings.get('auto_update', False):
            return

        logger.info("Auto-update enabled, checking for updates...")

        # Show checking status
        frame = self.renderer.render_menu("AUTO-UPDATE", ["Checking..."], -1, 0)
        self._display(frame, full_refresh=True)

        # Check for updates
        has_updates, msg = self.sys.check_for_updates()

        if has_updates:
            logger.info("Updates available, installing...")
            frame = self.renderer.render_menu("AUTO-UPDATE", ["Installing..."], -1, 0)
            self._display(frame, full_refresh=True)

            success, result_msg = self.sys.perform_update()
            if not success:
                logger.error(f"Auto-update failed: {result_msg}")
                frame = self.renderer.render_menu("AUTO-UPDATE", [f"Failed: {result_msg[:18]}"], -1, 0)
                self._display(frame, full_refresh=True)
                time.sleep(2)
            # If successful, perform_update will restart the app
        else:
            logger.info(f"Auto-update check: {msg}")

    def run(self):
        logger.info("Entering main loop")
        try:
            while True:
                # Wake display if sleeping and there was input
                if self._display_sleeping and self.inputs.has_pending_input():
                    self._wake_display()

                # Check for popup input routing first
                popup_callbacks = self.renderer.get_popup_callbacks()
                if popup_callbacks:
                    # Merge volume callbacks with popup callbacks
                    popup_callbacks['vol_up'] = self._vol_up
                    popup_callbacks['vol_down'] = self._vol_down
                    self.inputs.set_callbacks(popup_callbacks)
                elif self.current_app:
                    self.inputs.set_callbacks(self.current_app.get_callbacks())
                elif self.view == 'CONFIRM':
                    self.inputs.set_callbacks(self._get_confirm_callbacks())
                else:
                    self.inputs.set_callbacks(self._get_home_callbacks())

                if not self.inputs.check_inputs():
                    break

                self.sys.check_battery()

                frame = None
                force_full = False

                # Update Running App
                if self.current_app:
                    is_running = False
                    try:
                        is_running = self.current_app.update()
                    except Exception as e:
                        logger.error(f"App Update Error: {e}")
                        traceback.print_exc()

                    if hasattr(self.current_app, 'state') and getattr(self.current_app.state, 'needs_refresh', False):
                        force_full = True
                        self.current_app.state.needs_refresh = False

                    if not is_running:
                        self.close_app()
                    else:
                        frame = self.current_app.get_frame()
                else:
                    # Home Menu Logic
                    if self.view == 'HOME':
                        items = [n for _, n in self.registry.get_app_names()] + ["Reboot", "Shut Down"]
                        frame = self.renderer.render_menu("HOME MENU", items, self.menu_idx, 0)
                    elif self.view == 'CONFIRM':
                        frame = self._render_confirm()

                if frame:
                    # Render popups on top of frame
                    frame = self.renderer.render_with_popups(frame)
                    # Force refresh if a popup just expired
                    if self.renderer.popup_needs_refresh():
                        force_full = True
                    self._display(frame, force_full)

                    # Sleep display if screensaver is active (saves power)
                    if (self.current_app == self.music_app and
                        self.music_app.state.screensaver_image is not None and
                        not self._display_sleeping):
                        self._sleep_display()

                # Background updates
                if self.current_app != self.music_app:
                    self.music_app.update()

                time.sleep(0.05)

        except KeyboardInterrupt:
            logger.info("Keyboard Interrupt")
        except Exception as e:
            logger.critical(f"Critical Error: {e}")
            traceback.print_exc()
        finally:
            self.sys.sleep_display()

    def launch_app(self, app_id):
        app = self.registry.get_app(app_id)
        if app:
            logger.info(f"Launching app: {app_id}")
            self.current_app = app
            self.inputs.set_callbacks(app.get_callbacks())
            if hasattr(app, 'on_enter'):
                app.on_enter()
            if hasattr(app, 'refresh_list'):
                app.refresh_list()
            self.first_render = True

    def close_app(self):
        if self.current_app:
            if hasattr(self.current_app, 'on_exit'):
                self.current_app.on_exit()
        self.current_app = None
        self.view = 'HOME'
        self.inputs.set_callbacks(self._get_home_callbacks())
        self.first_render = True

    def _wake_display(self):
        """Wake display from sleep mode."""
        if self._display_sleeping:
            self.sys.wake_display()
            self._display_sleeping = False
            self.first_render = True  # Force full refresh on wake
            logger.debug("Display awakened from sleep")

    def _sleep_display(self):
        """Put display into sleep mode."""
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

    def _show_volume_popup(self, level):
        """Show or update volume popup."""
        # Check if there's already a volume popup
        popup = self.renderer.popups.peek()
        if popup and hasattr(popup, 'state') and popup.state and popup.state.extra.get('is_volume'):
            # Update existing popup
            popup.update(extra={'level': level, 'title': 'VOLUME', 'is_volume': True})
        else:
            # Create new volume popup
            popup = self.renderer.popups.show_volume("VOLUME", level)
            popup.state.extra['is_volume'] = True

    # --- Home Menu Interaction ---
    def _get_home_callbacks(self):
        return {
            'up': lambda: setattr(self, 'menu_idx', (self.menu_idx - 1) % (len(self.registry.get_all_apps()) + 2)),
            'down': lambda: setattr(self, 'menu_idx', (self.menu_idx + 1) % (len(self.registry.get_all_apps()) + 2)),
            'enter': self._handle_home_selection,
            'vol_up': self._vol_up,
            'vol_down': self._vol_down
        }

    def _handle_home_selection(self):
        apps = self.registry.get_app_names()
        count = len(apps)
        
        if self.menu_idx < count:
            app_id, _ = apps[self.menu_idx]
            self.launch_app(app_id)
        elif self.menu_idx == count: # Reboot
            self._start_confirm("REBOOT")
        elif self.menu_idx == count + 1: # Shutdown
            self._start_confirm("SHUTDOWN")

    # --- Confirmation Dialog ---
    def _start_confirm(self, target):
        self.view = 'CONFIRM'
        self.confirm_target = target
        self.confirm_idx = 0
        self.inputs.set_callbacks(self._get_confirm_callbacks())

    def _get_confirm_callbacks(self):
        return {
            'up': lambda: setattr(self, 'confirm_idx', 1 - self.confirm_idx),
            'down': lambda: setattr(self, 'confirm_idx', 1 - self.confirm_idx),
            'enter': self._handle_confirm,
            'back': self._cancel_confirm,
            'vol_up': self._vol_up,
            'vol_down': self._vol_down
        }

    def _render_confirm(self):
        title = f"CONFIRM {self.confirm_target}?"
        opts = ["No", "Yes"]
        return self.renderer.render_menu(title, opts, self.confirm_idx, 0)

    def _handle_confirm(self):
        if self.confirm_idx == 1:
            if self.confirm_target == "REBOOT":
                self._perform_system_action("REBOOTING...", self.sys.reboot)
            elif self.confirm_target == "SHUTDOWN":
                self._perform_shutdown()
        else:
            self._cancel_confirm()

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

    def _cancel_confirm(self):
        self.view = 'HOME'
        self.inputs.set_callbacks(self._get_home_callbacks())

    def _perform_system_action(self, msg, action):
        # Save volume before system action (reboot)
        self.settings_app.categories['AUDIO'].save_volume()

        frame = self.renderer.render_menu("SYSTEM", [msg], 0, 0)
        self._display(frame, full_refresh=True)
        time.sleep(2)
        action()

    def _handle_shutdown_request(self, reason="User Request"):
        logger.info(f"Shutdown requested: {reason}")
        if reason == "LOW BATTERY":
            frame = self.renderer.render_menu("LOW BATTERY", ["Shutting down..."], 0, 0)
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
        frame = self.renderer.render_menu("UPDATE", ["Checking..."], -1, 0)
        self._display(frame, full_refresh=True)

        # Check for updates
        has_updates, msg = self.sys.check_for_updates()

        if has_updates:
            frame = self.renderer.render_menu("UPDATE", ["Updating..."], -1, 0)
            self._display(frame, full_refresh=True)

            success, result_msg = self.sys.perform_update()
            if not success:
                frame = self.renderer.render_menu("UPDATE", [f"Error: {result_msg}"], -1, 0)
                self._display(frame, full_refresh=True)
                time.sleep(2)
        else:
            frame = self.renderer.render_menu("UPDATE", [msg], -1, 0)
            self._display(frame, full_refresh=True)
            time.sleep(1.5)

    def _perform_reset(self):
        """Reset all data files and reboot."""
        logger.info("Resetting data and rebooting")

        # Show resetting status
        frame = self.renderer.render_menu("RESET", ["Resetting data..."], -1, 0)
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

    # --- Display Wrapper ---
    def _display(self, img, full_refresh=False, skip_battery=False, skip_status=False):
        # Apply Overlays
        if not skip_status:
            img = self.renderer.overlays.draw_status_icons(
                img,
                self._check_audio_device(),
                self._check_wifi(),
                self._check_bluetooth()
            )
        if not skip_battery:
            img = self.renderer.overlays.draw_battery(img)

        if self.settings_app.invert_colors:
            from PIL import ImageOps
            img = ImageOps.invert(img.convert('L')).convert('1')

        # Check if frame changed (skip refresh if identical)
        frame_hash = hash(img.tobytes())
        if not full_refresh and not self.first_render and frame_hash == self._last_frame_hash:
            return  # No change, skip display update
        self._last_frame_hash = frame_hash

        # Check if periodic full refresh is needed (Waveshare e-paper precaution)
        needs_periodic_full = self._partial_refresh_count >= self._max_partial_refreshes

        epd = self.sys.get_display()
        if epd:
            try:
                buffer = epd.getbuffer(img.rotate(180))
                if self.first_render or full_refresh or needs_periodic_full:
                    epd.init()
                    epd.displayPartBaseImage(buffer)
                    self.first_render = False
                    self._partial_refresh_count = 0
                else:
                    epd.displayPartial(buffer)
                    self._partial_refresh_count += 1
            except Exception as e:
                logger.error(f"Display Error: {e}")

    # --- System Checks (Helpers) ---
    def _check_audio_device(self):
        # This could be moved to SystemManager too
        import subprocess
        try:
            r = subprocess.check_output(
                ["pactl", "get-default-sink"],
                text=True, stderr=subprocess.DEVNULL, timeout=2
            ).strip()
            if any(x in r.lower() for x in ['bluez', 'usb', 'headphone']):
                return True
        except (subprocess.SubprocessError, OSError):
            pass
        return False

    def _check_wifi(self):
        import subprocess
        try:
            r = subprocess.check_output(
                ["iwgetid", "-r"],
                text=True, stderr=subprocess.DEVNULL, timeout=2
            ).strip()
            return len(r) > 0
        except (subprocess.SubprocessError, OSError):
            return False

    def _check_bluetooth(self):
        import subprocess
        try:
            r = subprocess.check_output(
                ["rfkill", "list", "bluetooth"],
                text=True, stderr=subprocess.DEVNULL, timeout=2
            )
            return "Soft blocked: no" in r
        except (subprocess.SubprocessError, OSError):
            return False

if __name__ == "__main__":
    app = MainApp()
    app.run()