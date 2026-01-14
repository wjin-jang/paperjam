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
    print("WARNING: E-Paper drivers not found. Running in headless/text mode.")

class Launcher:
    def __init__(self):
        self.audio = AudioEngine()
        self.inputs = InputHandler()
        
        self.music_app = MusicPlayerApp(self.audio, self.inputs)
        self.settings_app = SettingsApp(self.music_app.lib, self.audio, self.inputs)

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

    def _init_hardware(self):
        if HAS_EPAPER:
            try:
                epd = epd2in13_V4.EPD()
                epd.init()
                epd.Clear(0xFF)
                return epd
            except Exception as e:
                print(f"EPD Init Error: {e}")
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
            print(f"LOW BATTERY ({pct}%) - Initiating safe shutdown...")
            self._perform_low_battery_shutdown()

    def _perform_low_battery_shutdown(self):
        """Perform safe shutdown due to low battery."""
        frame = self.renderer.render_menu("LOW BATTERY", ["Shutting down..."], 0, 0)
        self._display(frame, full_refresh=True)
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
        print("System Ready. Entering main loop...")
        try:
            while True:
                if not self.inputs.check_inputs(): break
                self._check_low_battery()
                frame = None

                force_full = False
                
                try:
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
                            frame = self.current_app.get_frame()
                    else:
                        if self.view == 'HOME':
                            frame = self.renderer.render_menu("HOME MENU", self.apps, self.idx, 0)
                        elif self.view == 'CONFIRM':
                            title = f"CONFIRM {self.confirm_target}?"
                            opts = ["No", "Yes"]
                            frame = self.renderer.render_menu(title, opts, self.confirm_idx, 0)

                    if frame: self._display(frame, force_full)

                except Exception as e:
                    print(f"Runtime Error: {e}")
                    traceback.print_exc()

                if self.current_app != self.music_app:
                    self.music_app.update()

                time.sleep(0.05) 

        except KeyboardInterrupt:
            print("Shutting down...")
        finally:
            if self.epd: self.epd.sleep()

    def _vol_up(self):
        """Global volume up handler."""
        self.settings_app.categories['AUDIO'].set_volume(5)

    def _vol_down(self):
        """Global volume down handler."""
        self.settings_app.categories['AUDIO'].set_volume(-5)

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
        print(f"Launching: {name}")
        
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
        print("Initiating Shutdown Sequence...")
        cover = self.music_app.lib.get_random_cover()
        frame = self.renderer.render_shutdown(cover)
        self._display(frame, full_refresh=True, skip_battery=True)
        time.sleep(3)
        if self.epd:
            try: self.epd.sleep()
            except: pass
        subprocess.run(["sudo", "shutdown", "now"])

    def _draw_battery(self, img):
        """Overlay battery icon on top right corner."""
        battery = get_battery_monitor()
        pct = battery.percentage
        if pct < 0:
            return img

        # Use battery icon font if available
        if cfg.FONT_BATTERY:
            # Map percentage to icon 0-8
            icon_num = min(8, max(0, round(pct / 12.5)))
            icon = str(icon_num)
            if battery.charging:
                icon = "C" + icon

            draw = ImageDraw.Draw(img)
            bbox = draw.textbbox((0, 0), icon, font=cfg.FONT_BATTERY)
            text_w = bbox[2] - bbox[0]
            x = cfg.SCREEN_WIDTH - text_w - 8
            y = 0

            draw.text((x, y), icon, font=cfg.FONT_BATTERY, fill=cfg.BLACK)
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

    def _display(self, img, full_refresh=False, skip_battery=False):
        # Overlay battery indicator
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
                print(f"Display Error: {e}")

if __name__ == "__main__":
    Launcher().run()
