import time
import sys
import traceback
import subprocess
from PIL import Image, ImageOps, ImageDraw

import config as cfg
from core.audio import AudioEngine
from core.inputs import InputHandler
from core.battery import get_battery_monitor
from apps.music import MusicPlayerApp  # Now imports from the package
from apps.settings import SettingsApp
from ui.renderer import UIRenderer

try:
    from waveshare_epd import epd2in13_V4
    HAS_EPAPER = True
except ImportError:
    HAS_EPAPER = False
    print("WARNING: E-Paper drivers not found. Running in headless/text mode.", flush=True)

class Launcher:
    def __init__(self):
        self.audio = AudioEngine()
        self.inputs = InputHandler()
        
        self.music_app = MusicPlayerApp(self.audio, self.inputs)
        self.settings_app = SettingsApp(self.music_app.lib, self.audio, self.inputs)
        # Share settings manager with music player for endless playback feature
        self.music_app.set_settings(self.settings_app.settings)
        # Set callback for screen clear shutdown
        self.settings_app.categories['SYSTEM'].set_screen_clear_callback(self._perform_screen_clear_shutdown)

        self.renderer = UIRenderer()
        self.epd = self._init_hardware()

        # Set display callback for loading overlays
        self.music_app.set_display_callback(lambda img: self._display(img))

        # Set volume callbacks for music player
        self.music_app.set_volume_callbacks(
            lambda: self.settings_app.categories['AUDIO'].set_volume(5),
            lambda: self.settings_app.categories['AUDIO'].set_volume(-5)
        )
        
        self.apps = ["Music Player", "System Settings", "Reboot", "Shut Down"]
        self.idx = 0
        self.current_app = None
        self.first_render = True
        
        self.view = 'HOME'
        self.confirm_target = None
        self.confirm_idx = 0
        self.input_lock_time = 0
        
        self.inputs.set_callbacks(self._get_launcher_cb())

        # Low battery shutdown
        self._last_battery_check = 0
        self._low_battery_threshold = 12  # Shutdown at 12% (lowest non-zero level)

        # Volume overlay
        self._volume_display_time = 0
        self._volume_display_duration = 1.5  # Show volume for 1.5 seconds

    def _init_hardware(self):
        if HAS_EPAPER:
            try:
                epd = epd2in13_V4.EPD()
                epd.init()
                epd.Clear(0xFF)
                return epd
            except Exception as e:
                print(f"EPD Init Error: {e}", flush=True)
        return None

    def _check_low_battery(self):
        """Check battery and shutdown if critically low."""
        now = time.time()
        if now - self._last_battery_check < 60:  # Check every 60 seconds
            return
        self._last_battery_check = now

        battery = get_battery_monitor()
        pct = battery.percentage
        if pct >= 0 and pct <= self._low_battery_threshold and not battery.charging:
            print(f"LOW BATTERY ({pct}%) - Initiating safe shutdown...", flush=True)
            self._perform_low_battery_shutdown()

    def _perform_low_battery_shutdown(self):
        """Perform safe shutdown due to low battery."""
        frame = self.renderer.render_menu("LOW BATTERY", ["Shutting down..."], 0, 0)
        # Show empty battery icon during low battery shutdown
        frame = self._draw_battery(frame, show_empty=True)
        self._display(frame, full_refresh=True, skip_battery=True, skip_status=True)
        time.sleep(2)
        if self.epd:
            try:
                self.epd.init()
                self.epd.Clear(0xFF)
                self.epd.sleep()
            except:
                pass
        subprocess.run(["sudo", "shutdown", "now"])

    def run(self):
        print("System Ready. Entering main loop...", flush=True)
        try:
            while True:
                if not self.inputs.check_inputs(): break
                self._check_low_battery()
                frame = None

                force_full = False
                
                try:
                    # Check if volume overlay should be shown
                    show_volume = time.time() - self._volume_display_time < self._volume_display_duration

                    if self.current_app:
                        is_running = False
                        if hasattr(self.current_app, 'update'):
                            is_running = self.current_app.update()

                        if hasattr(self.current_app, 'state') and getattr(self.current_app.state, 'needs_refresh', False):
                            force_full = True
                            self.current_app.state.needs_refresh = False

                        if not is_running:
                            self.current_app = None
                            self.view = 'HOME'
                            self.inputs.set_callbacks(self._get_launcher_cb())
                            self.first_render = True
                        else:
                            # Show volume overlay if recently changed, otherwise show app frame
                            if show_volume and self.current_app != self.settings_app:
                                volume = self.settings_app.categories['AUDIO'].volume_level
                                frame = self.renderer.render_volume("VOLUME", volume)
                            else:
                                frame = self.current_app.get_frame()
                    else:
                        if show_volume:
                            volume = self.settings_app.categories['AUDIO'].volume_level
                            frame = self.renderer.render_volume("VOLUME", volume)
                        elif self.view == 'HOME':
                            frame = self.renderer.render_menu("HOME MENU", self.apps, self.idx, 0)
                        elif self.view == 'CONFIRM':
                            title = f"CONFIRM {self.confirm_target}?"
                            opts = ["No", "Yes"]
                            frame = self.renderer.render_menu(title, opts, self.confirm_idx, 0)

                    if frame: self._display(frame, force_full)

                except Exception as e:
                    print(f"Runtime Error: {e}", flush=True)
                    traceback.print_exc()

                if self.current_app != self.music_app:
                    self.music_app.update()

                time.sleep(0.05) 

        except KeyboardInterrupt:
            print("Shutting down...", flush=True)
        finally:
            if self.epd: self.epd.sleep()

    def _vol_up(self):
        """Global volume up handler."""
        self.settings_app.categories['AUDIO'].set_volume(5)
        self._volume_display_time = time.time()

    def _vol_down(self):
        """Global volume down handler."""
        self.settings_app.categories['AUDIO'].set_volume(-5)
        self._volume_display_time = time.time()

    def _get_launcher_cb(self):
        return {
            'up': lambda: setattr(self, 'idx', (self.idx - 1) % len(self.apps)),
            'down': lambda: setattr(self, 'idx', (self.idx + 1) % len(self.apps)),
            'enter': self._launch,
            'vol_up': self._vol_up,
            'vol_down': self._vol_down
        }

    def _get_confirm_cb(self):
        return {
            'up': lambda: setattr(self, 'confirm_idx', 1 - self.confirm_idx),
            'down': lambda: setattr(self, 'confirm_idx', 1 - self.confirm_idx),
            'enter': self._handle_confirm_selection,
            'back': self._cancel_confirm,
            'vol_up': self._vol_up,
            'vol_down': self._vol_down
        }

    def _launch(self):
        name = self.apps[self.idx]
        print(f"Launching: {name}", flush=True)
        
        if name == "Music Player":
            self.current_app = self.music_app
            self.inputs.set_callbacks(self.music_app.get_callbacks())
            self.music_app.refresh_list()
            self.first_render = True 
            
        elif name == "System Settings":
            self.current_app = self.settings_app
            self.settings_app.running = True 
            self.inputs.set_callbacks(self.settings_app.get_callbacks())
            self.first_render = True 

        elif name == "Reboot":
            self._start_confirmation("REBOOT")

        elif name == "Shut Down":
            self._start_confirmation("SHUTDOWN")

    def _start_confirmation(self, target):
        self.view = 'CONFIRM'
        self.confirm_target = target
        self.confirm_idx = 0 
        self.input_lock_time = time.time() 
        self.inputs.set_callbacks(self._get_confirm_cb())

    def _handle_confirm_selection(self):
        if time.time() - self.input_lock_time < 0.5:
            return 

        if self.confirm_idx == 1: 
            if self.confirm_target == "REBOOT":
                self._perform_system_action("REBOOTING...", ["sudo", "reboot"])
            elif self.confirm_target == "SHUTDOWN":
                self._perform_shutdown()
        else:
            self._cancel_confirm()

    def _cancel_confirm(self):
        self.view = 'HOME'
        self.inputs.set_callbacks(self._get_launcher_cb())

    def _perform_system_action(self, message, command, clear_screen=True):
        frame = self.renderer.render_menu("SYSTEM", [message], 0, 0)
        self._display(frame, full_refresh=True)
        time.sleep(2.5) 
        if clear_screen and self.epd:
            try:
                self.epd.init()
                self.epd.Clear(0xFF)
                self.epd.sleep()
            except: pass
        subprocess.run(command)

    def _perform_shutdown(self):
        print("Initiating Shutdown Sequence...", flush=True)
        cover = self.music_app.lib.get_random_cover()
        frame = self.renderer.render_shutdown(cover)
        self._display(frame, full_refresh=True, skip_battery=True, skip_status=True)
        time.sleep(3)
        if self.epd:
            try: self.epd.sleep()
            except: pass
        subprocess.run(["sudo", "shutdown", "now"])

    def _perform_screen_clear_shutdown(self):
        """Clear the screen and shutdown - useful for screen removal/replacement."""
        print("Clearing screen and shutting down...", flush=True)
        if self.epd:
            try:
                self.epd.init()
                self.epd.Clear(0xFF)  # Clear to white
                self.epd.sleep()
            except Exception as e:
                print(f"Screen clear error: {e}", flush=True)
        subprocess.run(["sudo", "shutdown", "now"])

    def _is_audio_device_connected(self):
        """Check if an external audio device (headphones, bluetooth) is connected."""
        # Try PulseAudio first
        try:
            result = subprocess.check_output(
                ["pactl", "get-default-sink"],
                text=True, stderr=subprocess.DEVNULL, timeout=1
            ).strip()
            # Check if it's a bluetooth or USB device
            if 'bluez' in result.lower() or 'usb' in result.lower() or 'headphone' in result.lower():
                return True
            # Also check if bluetooth audio is connected
            bt_result = subprocess.check_output(
                ["pactl", "list", "short", "sinks"],
                text=True, stderr=subprocess.DEVNULL, timeout=1
            )
            if 'bluez' in bt_result.lower():
                return True
        except Exception:
            pass
        # Fallback: check if any bluetooth audio device is connected via bluetoothctl
        try:
            result = subprocess.check_output(
                ["bluetoothctl", "info"],
                text=True, stderr=subprocess.DEVNULL, timeout=1
            )
            if 'Connected: yes' in result and ('audio' in result.lower() or 'headset' in result.lower()):
                return True
        except Exception:
            pass
        return False

    def _is_wifi_connected(self):
        """Check if WiFi is connected."""
        try:
            # Check if wlan0 has an IP address
            result = subprocess.check_output(
                ["iwgetid", "-r"],
                text=True, stderr=subprocess.DEVNULL, timeout=1
            ).strip()
            return len(result) > 0
        except Exception:
            pass
        return False

    def _is_bluetooth_enabled(self):
        """Check if Bluetooth is enabled (not soft-blocked)."""
        try:
            result = subprocess.check_output(
                ["rfkill", "list", "bluetooth"],
                text=True, stderr=subprocess.DEVNULL, timeout=1
            )
            return "Soft blocked: no" in result
        except Exception:
            pass
        return False

    def _draw_status_icons(self, img):
        """Draw status icons (headphones, wifi, bluetooth) on top left corner."""
        if not cfg.FONT_ICONS:
            return img

        icons = ""
        # H = Headphones (audio device connected)
        if self._is_audio_device_connected():
            icons += "H"
        # W = WiFi connected
        if self._is_wifi_connected():
            icons += "W"
        # B = Bluetooth enabled
        if self._is_bluetooth_enabled():
            icons += "B"

        if icons:
            draw = ImageDraw.Draw(img)
            x = 8  # Padding from left
            y = 0
            draw.text((x, y), icons, font=cfg.FONT_ICONS, fill=cfg.BLACK)

        return img

    def _draw_battery(self, img, show_empty=False):
        """Overlay battery icon on top right corner.

        Args:
            img: Image to draw on
            show_empty: If True, allow showing icon 0 (empty battery).
                       Otherwise minimum icon is 1.
        """
        battery = get_battery_monitor()
        pct = battery.percentage
        if pct < 0:
            return img

        # Use battery icon font if available
        if cfg.FONT_ICONS:
            # Map percentage to icon 0-8
            icon_num = min(8, max(0, round(pct / 12.5)))
            # Don't show empty battery icon (0) unless explicitly allowed
            # (e.g., during safe shutdown)
            if not show_empty and icon_num == 0:
                icon_num = 1
            icon = str(icon_num)
            if battery.charging:
                icon = "C" + icon

            draw = ImageDraw.Draw(img)
            bbox = draw.textbbox((0, 0), icon, font=cfg.FONT_ICONS)
            text_w = bbox[2] - bbox[0]
            x = cfg.SCREEN_WIDTH - text_w - 8
            y = 0

            draw.text((x, y), icon, font=cfg.FONT_ICONS, fill=cfg.BLACK)
        else:
            # Fallback to text
            text = battery.get_display_text()
            if not text:
                return img

            draw = ImageDraw.Draw(img)
            bbox = draw.textbbox((0, 0), text, font=cfg.FONT_MAIN)
            text_w = bbox[2] - bbox[0]
            x = cfg.SCREEN_WIDTH - text_w - 4
            y = 0

            draw.text((x, y), text, font=cfg.FONT_MAIN, fill=cfg.BLACK)

        return img

    def _display(self, img, full_refresh=False, skip_battery=False, skip_status=False):
        # Overlay status icons (headphones, wifi, bluetooth) on top left
        if not skip_status:
            img = self._draw_status_icons(img)
        # Overlay battery indicator on top right
        if not skip_battery:
            img = self._draw_battery(img)

        # Invert colors if enabled
        if self.settings_app.invert_colors:
            img = ImageOps.invert(img.convert('L')).convert('1')

        if self.epd:
            try:
                buffer = self.epd.getbuffer(img.rotate(180))
                if self.first_render or full_refresh:
                    self.epd.init()
                    self.epd.displayPartBaseImage(buffer)
                    self.first_render = False
                else:
                    self.epd.displayPartial(buffer)
            except Exception as e:
                print(f"Display Error: {e}", flush=True)

if __name__ == "__main__":
    Launcher().run()
