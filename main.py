import time
import sys
import traceback
from PIL import Image

import config as cfg
from core.audio import AudioEngine
from core.inputs import InputHandler
from core.system import SystemManager
from core.logger import setup_logger
from core.app_registry import AppRegistry
from ui.renderer import UIRenderer

from apps.music import MusicPlayerApp
from apps.settings import SettingsApp

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
        
        # Display/Overlay State
        self.first_render = True
        self.volume_display_time = 0
        self.volume_display_duration = 1.5

        # Setup Global Callbacks
        self.sys.on_shutdown_request = self._handle_shutdown_request
        self.settings_app.categories['SYSTEM'].set_screen_clear_callback(self._perform_screen_clear_shutdown)
        
        # Music App Display Callback
        self.music_app.set_display_callback(lambda img: self._display(img))
        
        # Volume Callbacks (Global)
        self.music_app.set_volume_callbacks(self._vol_up, self._vol_down)

        # Initial Input Setup
        self.inputs.set_callbacks(self._get_home_callbacks())

        # First Run
        if self.music_app.lib.is_first_run():
            self._run_first_startup()

    def _run_first_startup(self):
        """Handle first run - show welcome screen with options."""
        logger.info("First run detected")

        # Show initial choice screen
        choice = self._show_startup_choice()

        if choice == 'shutdown':
            logger.info("User chose to shutdown for library setup")
            frame = self.renderer.render_menu("SETUP", [
                "Shutting down...",
                "",
                "Add music to:",
                f"{cfg.MUSIC_PATH}"
            ], -1, 0)
            self._display(frame, full_refresh=True)
            time.sleep(2)
            self.sys.shutdown()
            return

        # User chose to scan
        self._run_library_scan()

    def _show_startup_choice(self):
        """Show startup choice screen - scan now or shutdown to add music.

        Returns:
            'scan' or 'shutdown'
        """
        choice_idx = 0
        choice_made = False
        result = 'scan'

        def on_up():
            nonlocal choice_idx
            choice_idx = (choice_idx - 1) % 2

        def on_down():
            nonlocal choice_idx
            choice_idx = (choice_idx + 1) % 2

        def on_enter():
            nonlocal choice_made, result
            result = 'scan' if choice_idx == 0 else 'shutdown'
            choice_made = True

        # Set temporary callbacks for this screen
        self.inputs.set_callbacks({
            'up': on_up,
            'down': on_down,
            'enter': on_enter
        })

        while not choice_made:
            if not self.inputs.check_inputs():
                break

            items = [
                "Welcome to PaperJam!",
                "",
                "Music path:",
                f"{str(cfg.MUSIC_PATH)[:22]}",
                "",
                "Scan Library Now",
                "Shutdown (Add Music)"
            ]
            # Selection is on items 5 or 6 (0-indexed)
            sel_idx = 5 + choice_idx

            frame = self.renderer.render_menu("FIRST RUN", items, sel_idx, 0)
            self._display(frame, full_refresh=self.first_render)
            self.first_render = False
            time.sleep(0.05)

        self.first_render = True
        return result

    def _run_library_scan(self):
        """Run library scan with progress display."""
        logger.info("Starting library scan")
        self.music_app.lib.scan_async(force=True)

        while self.music_app.lib.is_scanning:
            lib = self.music_app.lib
            items = [
                "Scanning library...",
                "",
                f"Tracks: {lib.scan_track_count}",
                f"Albums: {lib.scan_album_count}",
                f"Artists: {lib.scan_artist_count}"
            ]
            if lib.scan_current_file:
                items.append("")
                items.append(f"{lib.scan_current_file[:22]}")

            frame = self.renderer.render_menu("SCANNING", items, -1, 0)
            self._display(frame, full_refresh=self.first_render)
            self.first_render = False
            time.sleep(0.1)

        self.first_render = True
        logger.info(f"Scan complete: {self.music_app.lib.scan_track_count} tracks")

        # Show welcome screen with tiled album art
        self._show_welcome_screen()

    def _show_welcome_screen(self):
        """Show welcome screen with tiled album covers and continue button."""
        # Get random covers for tiling
        covers = self.music_app.lib.get_random_covers(count=15, small=True)

        # Wait for user to press enter
        continue_pressed = False

        def on_enter():
            nonlocal continue_pressed
            continue_pressed = True

        self.inputs.set_callbacks({
            'enter': on_enter,
            'up': lambda: None,
            'down': lambda: None
        })

        while not continue_pressed:
            if not self.inputs.check_inputs():
                break

            frame = self.renderer.render_welcome_tiled(covers)
            self._display(frame, full_refresh=self.first_render, skip_battery=True, skip_status=True)
            self.first_render = False
            time.sleep(0.05)

        self.first_render = True

    def run(self):
        logger.info("Entering main loop")
        try:
            while True:
                if not self.inputs.check_inputs():
                    break
                
                self.sys.check_battery()
                
                frame = None
                force_full = False
                
                # Check Overlays
                show_volume = time.time() - self.volume_display_time < self.volume_display_duration
                
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
                        # Render App or Overlay
                        if show_volume and self.current_app != self.settings_app:
                            vol = self.settings_app.categories['AUDIO'].volume_level
                            frame = self.renderer.render_volume("VOLUME", vol)
                        else:
                            frame = self.current_app.get_frame()
                else:
                    # Home Menu Logic
                    if show_volume:
                        vol = self.settings_app.categories['AUDIO'].volume_level
                        frame = self.renderer.render_volume("VOLUME", vol)
                    elif self.view == 'HOME':
                        items = [n for _, n in self.registry.get_app_names()] + ["Reboot", "Shut Down"]
                        frame = self.renderer.render_menu("HOME MENU", items, self.menu_idx, 0)
                    elif self.view == 'CONFIRM':
                        frame = self._render_confirm()

                if frame:
                    self._display(frame, force_full)

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

    def _vol_up(self):
        self.settings_app.categories['AUDIO'].set_volume(5)
        self.volume_display_time = time.time()

    def _vol_down(self):
        self.settings_app.categories['AUDIO'].set_volume(-5)
        self.volume_display_time = time.time()

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

        epd = self.sys.get_display()
        if epd:
            try:
                buffer = epd.getbuffer(img.rotate(180))
                if self.first_render or full_refresh:
                    epd.init()
                    epd.displayPartBaseImage(buffer)
                    self.first_render = False
                else:
                    epd.displayPartial(buffer)
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