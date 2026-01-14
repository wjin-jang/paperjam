import time
import subprocess
import json
from pathlib import Path
from ui.renderer import UIRenderer
from core.bluetooth import BluetoothManager
import config as cfg

class SettingsApp:
    def __init__(self, library_manager, audio_engine, input_handler):
        self.renderer = UIRenderer()
        self.lib = library_manager
        self.audio = audio_engine
        self.bt = BluetoothManager()
        self.input = input_handler
        
        self.main_menu = ["Audio", "Library", "Network", "System", "Display"]
        
        self.view = 'MAIN'
        self.idx = 0
        self.submenu_idx = 0
        self.current_category = ""
        self.current_submenu = []
        
        self.running = True
        
        # Defaults (will be overwritten by load_settings)
        self.invert_colors = False
        self.audio_output = "Auto"
        
        # Load saved preferences immediately
        self._load_settings()
        
        self.volume_level = 50
        self._init_volume()
        
        self.bt_devices = []
        self.bt_idx = 0
        self.bt_status = "Idle"

    def _get_settings_file(self):
        # Ensure DATA_DIR exists (it's created in library.py, but safe to check)
        cfg.DATA_DIR.mkdir(parents=True, exist_ok=True)
        return cfg.DATA_DIR / "settings.json"

    def _load_settings(self):
        """Loads settings from JSON and updates config.py globals."""
        settings_path = self._get_settings_file()
        if settings_path.exists():
            try:
                with open(settings_path, 'r') as f:
                    data = json.load(f)
                    
                    # App State
                    self.invert_colors = data.get('invert_colors', False)
                    self.audio_output = data.get('audio_output', 'Auto')
                    
                    # Config Globals
                    if 'recents_limit' in data:
                        cfg.RECENTS_LIMIT = data['recents_limit']
                    if 'screensaver_timeout' in data:
                        cfg.SCREENSAVER_TIMEOUT = data['screensaver_timeout']
                    if 'long_press_duration' in data:
                        cfg.LONG_PRESS_DURATION = data['long_press_duration']
                        
            except Exception as e:
                print(f"Error loading settings: {e}")

    def _save_settings(self):
        """Saves current settings to JSON."""
        data = {
            'invert_colors': self.invert_colors,
            'audio_output': self.audio_output,
            'recents_limit': cfg.RECENTS_LIMIT,
            'screensaver_timeout': cfg.SCREENSAVER_TIMEOUT,
            'long_press_duration': cfg.LONG_PRESS_DURATION
        }
        try:
            with open(self._get_settings_file(), 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def _init_volume(self):
        try:
            cmd = "amixer get Master | grep -o '[0-9]*%' | head -1"
            res = subprocess.check_output(cmd, shell=True, text=True).strip().replace('%', '')
            self.volume_level = int(res)
        except: self.volume_level = 50

    def _set_volume(self, change):
        self.volume_level = max(0, min(100, self.volume_level + change))
        try:
            subprocess.run(["amixer", "set", "Master", f"{self.volume_level}%"], stdout=subprocess.DEVNULL)
        except: pass

    def get_callbacks(self):
        return {
            'up': self.nav_up,
            'down': self.nav_down,
            'left': self.nav_left,
            'right': self.nav_right,
            'enter': self.nav_enter,
            'back': self.nav_back
        }

    def update(self):
        if self.view == 'SUBMENU' and self.current_category == "LIBRARY":
            self._update_library_submenu()
        return self.running

    def _get_wifi_info(self):
        try:
            ssid = subprocess.check_output("iwgetid -r", shell=True, text=True).strip()
            ip = subprocess.check_output(['hostname', '-I'], encoding='utf-8').split()[0]
            return f"{ssid} ({ip})"
        except: return "Disconnected"

    def _get_disk_usage(self):
        try:
            return subprocess.check_output("df -h / | grep / | awk '{print $4}'", shell=True, text=True).strip() + " Free"
        except: return "Unknown"

    # --- Navigation ---
    def nav_up(self):
        if self.view == 'VOLUME':
            self._set_volume(5)
            return
        if self.view == 'MAIN':
            self.idx = (self.idx - 1) % len(self.main_menu)
        elif self.view == 'SUBMENU':
            self.submenu_idx = (self.submenu_idx - 1) % len(self.current_submenu)
        elif self.view in ['BT_SAVED', 'BT_SCAN']:
            limit = len(self.bt_devices) + (1 if self.view == 'BT_SAVED' else 0)
            if limit > 0: self.bt_idx = (self.bt_idx - 1) % limit

    def nav_down(self):
        if self.view == 'VOLUME':
            self._set_volume(-5)
            return
        if self.view == 'MAIN':
            self.idx = (self.idx + 1) % len(self.main_menu)
        elif self.view == 'SUBMENU':
            self.submenu_idx = (self.submenu_idx + 1) % len(self.current_submenu)
        elif self.view in ['BT_SAVED', 'BT_SCAN']:
            limit = len(self.bt_devices) + (1 if self.view == 'BT_SAVED' else 0)
            if limit > 0: self.bt_idx = (self.bt_idx + 1) % limit

    def nav_left(self):
        if self.view == 'VOLUME': self._set_volume(-5)

    def nav_right(self):
        if self.view == 'VOLUME': self._set_volume(5)

    def nav_enter(self):
        if self.view == 'VOLUME':
            self.view = 'SUBMENU'
            return
        if self.view == 'MAIN':
            self._enter_category(self.main_menu[self.idx])
        elif self.view == 'SUBMENU':
            self._handle_submenu_action()
        elif self.view == 'BT_SAVED':
            if self.bt_idx == len(self.bt_devices):
                self.view = 'BT_SCAN'
                self.bt_idx = 0
                self.bt_status = "Scanning..."
                self.bt_devices = []
                self.bt.start_scan(self._bt_scan_callback)
            else:
                if self.bt_devices:
                    dev = self.bt_devices[self.bt_idx]
                    self.bt_status = f"Connecting to {dev['name']}..."
                    self.bt.connect_async(dev['mac'], self._bt_connect_callback)
        elif self.view == 'BT_SCAN':
            if self.bt_devices:
                dev = self.bt_devices[self.bt_idx]
                self.bt.stop_scan()
                self.bt_status = f"Pairing {dev['name']}..."
                self.bt.connect_async(dev['mac'], self._bt_connect_callback)

    def nav_back(self):
        if self.view == 'VOLUME':
            self.view = 'SUBMENU'
        elif self.view == 'BT_SCAN':
            self.bt.stop_scan()
            self._enter_bt_saved_view()
        elif self.view == 'BT_SAVED':
            self.view = 'SUBMENU'
        elif self.view == 'SUBMENU':
            self.view = 'MAIN'
            self.submenu_idx = 0
        elif self.view == 'MAIN':
            self.running = False
        return True

    # --- Logic ---
    def _enter_category(self, category):
        self.current_category = category.upper()
        self.submenu_idx = 0
        
        if category == "Audio":
            self.current_submenu = [
                f"Output: {self.audio_output}",
                "Volume",
                "Bluetooth Manager"
            ]
            self.view = 'SUBMENU'
            
        elif category == "Library":
            self._update_library_submenu()
            self.view = 'SUBMENU'
            
        elif category == "Network":
            self.current_submenu = [f"WiFi: {self._get_wifi_info()}", "Bluetooth Status"]
            self.view = 'SUBMENU'
            
        elif category == "Display":
            state = "ON" if self.invert_colors else "OFF"
            ss_timeout = "OFF" if cfg.SCREENSAVER_TIMEOUT == 0 else f"{cfg.SCREENSAVER_TIMEOUT}s"
            
            self.current_submenu = [
                f"Invert Colors: {state}",
                f"Screensaver: {ss_timeout}"
            ]
            self.view = 'SUBMENU'
            
        elif category == "System":
            self.current_submenu = [
                self._get_disk_usage(),
                f"Long Press: {cfg.LONG_PRESS_DURATION}s",
                "Version 1.5",
                "Restart System"
            ]
            self.view = 'SUBMENU'

    def _update_library_submenu(self):
        status = " (Scanning...)" if self.lib.is_scanning else ""
        self.current_submenu = [
            "Reload Library",
            f"Recents Limit: {cfg.RECENTS_LIMIT}",
            f"Tracks: {self.lib.get_total_tracks()}{status}",
            f"Albums: {len(self.lib.albums)}",
            f"Artists: {len(self.lib.artists)}"
        ]

    def _enter_bt_saved_view(self):
        self.view = 'BT_SAVED'
        self.bt_status = "Select Device"
        self.bt_devices = self.bt.get_paired_devices()
        self.bt_idx = 0

    def _cycle_val(self, current, options):
        try:
            idx = options.index(current)
            return options[(idx + 1) % len(options)]
        except: return options[0]

    def _handle_submenu_action(self):
        cat = self.current_category
        item_text = self.current_submenu[self.submenu_idx]
        
        # Flag to trigger save
        should_save = False

        if cat == "AUDIO":
            if "Bluetooth" in item_text:
                self._enter_bt_saved_view()
            elif "Volume" in item_text:
                self.view = 'VOLUME'
                self._init_volume()
            elif "Output" in item_text:
                modes = ["Auto", "Headphones", "HDMI"]
                try: curr_i = modes.index(self.audio_output)
                except: curr_i = 0
                self.audio_output = modes[(curr_i + 1) % len(modes)]
                self.current_submenu[self.submenu_idx] = f"Output: {self.audio_output}"
                should_save = True

        elif cat == "LIBRARY":
            if "Reload Library" in item_text:
                self.lib.scan_async(force=True)
                self._show_popup("Rescanning...")
            elif "Recents Limit" in item_text:
                new_val = self._cycle_val(cfg.RECENTS_LIMIT, cfg.RECENTS_OPTIONS)
                cfg.RECENTS_LIMIT = new_val
                self._update_library_submenu()
                should_save = True

        elif cat == "DISPLAY":
            if "Invert Colors" in item_text:
                self.invert_colors = not self.invert_colors
                self.current_submenu[self.submenu_idx] = f"Invert Colors: {'ON' if self.invert_colors else 'OFF'}"
                should_save = True
            elif "Screensaver" in item_text:
                new_val = self._cycle_val(cfg.SCREENSAVER_TIMEOUT, cfg.SCREENSAVER_OPTIONS)
                cfg.SCREENSAVER_TIMEOUT = new_val
                val_str = "OFF" if new_val == 0 else f"{new_val}s"
                self.current_submenu[self.submenu_idx] = f"Screensaver: {val_str}"
                should_save = True

        elif cat == "SYSTEM":
            if "Restart" in item_text:
                subprocess.run(["sudo", "reboot"])
            elif "Long Press" in item_text:
                new_val = self._cycle_val(cfg.LONG_PRESS_DURATION, cfg.LONG_PRESS_OPTIONS)
                cfg.LONG_PRESS_DURATION = new_val
                self.current_submenu[self.submenu_idx] = f"Long Press: {new_val}s"
                should_save = True
        
        # Save immediately if a setting changed
        if should_save:
            self._save_settings()

    def _show_popup(self, msg):
        self.popup_msg = msg
        self.prev_view = self.view
        self.view = 'POPUP'
        self.popup_start = time.time()

    def _bt_scan_callback(self, devices):
        self.bt_devices = devices

    def _bt_connect_callback(self, success, msg):
        self.bt_status = msg
        if success and self.view == 'BT_SCAN':
             self.bt.stop_scan()

    def get_frame(self):
        if self.view == 'VOLUME':
            return self.renderer.render_volume("VOLUME", self.volume_level)

        if self.view == 'POPUP':
            is_busy = self.lib.is_scanning or (time.time() - self.popup_start < 1.5)
            if not is_busy: self.view = self.prev_view
            else: return self.renderer.render_menu("PLEASE WAIT", [self.popup_msg], 0, 0)

        if self.view == 'MAIN':
            return self.renderer.render_menu("SETTINGS", self.main_menu, self.idx, 0)
        
        elif self.view == 'SUBMENU':
            return self.renderer.render_menu(self.current_category, self.current_submenu, self.submenu_idx, 0)

        elif self.view == 'BT_SAVED':
            display_list = []
            for d in self.bt_devices:
                is_conn = self.bt.is_connected(d['mac'])
                prefix = "C" if is_conn else "P"
                display_list.append(f"{prefix} {d['name']}")
            display_list.append("[ Scan New Device ]")
            return self.renderer.render_menu(f"BT: {self.bt_status}", display_list, self.bt_idx, 0)

        elif self.view == 'BT_SCAN':
            if not self.bt_devices: display_list = ["(Scanning...)"]
            else: 
                display_list = []
                for d in self.bt_devices:
                     icon = "P" if d.get('paired') else " "
                     display_list.append(f"{icon} {d['name']}")
            return self.renderer.render_menu(f"BT: {self.bt_status}", display_list, self.bt_idx, 0)
