import time
import sys
import traceback
import subprocess
from PIL import Image, ImageOps # --- ADDED ImageOps

from core.audio import AudioEngine
from core.inputs import InputHandler
from apps.music import MusicPlayerApp
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
        
        self.apps = ["Music Player", "System Settings", "Reboot", "Shut Down"]
        self.idx = 0
        self.current_app = None
        self.first_render = True
        
        self.view = 'HOME'
        self.confirm_target = None
        self.confirm_idx = 0
        self.input_lock_time = 0
        
        self.inputs.set_callbacks(self._get_launcher_cb())

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

    def run(self):
        print("System Ready. Entering main loop...")
        try:
            while True:
                if not self.inputs.check_inputs(): break 
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

    def _get_launcher_cb(self):
        return {
            'up': lambda: setattr(self, 'idx', (self.idx - 1) % len(self.apps)),
            'down': lambda: setattr(self, 'idx', (self.idx + 1) % len(self.apps)),
            'enter': self._launch
        }

    def _get_confirm_cb(self):
        return {
            'up': lambda: setattr(self, 'confirm_idx', 1 - self.confirm_idx),
            'down': lambda: setattr(self, 'confirm_idx', 1 - self.confirm_idx),
            'enter': self._handle_confirm_selection,
            'back': self._cancel_confirm
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
        self._display(frame, full_refresh=True)
        time.sleep(3)
        if self.epd:
            try: self.epd.sleep()
            except: pass
        subprocess.run(["sudo", "shutdown", "now"])

    def _display(self, img, full_refresh=False):
        # --- FIX: Invert Colors Implementation ---
        # Check settings_app state and apply inversion if needed
        if self.settings_app.invert_colors:
             # Convert to L (Greyscale) -> Invert -> Convert back to 1-bit
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
