import time
import subprocess
import json
from pathlib import Path
from ui.renderer import UIRenderer
from core.bluetooth import BluetoothManager
from core.navigation import nav_index_up, nav_index_down
from core.settings_manager import get_settings_manager
import config as cfg

class SettingsApp:
    def __init__(self, library_manager, audio_engine, input_handler):
        self.renderer = UIRenderer()
        self.lib = library_manager
        self.audio = audio_engine
        self.bt = BluetoothManager()
        self.input = input_handler
        self.settings = get_settings_manager()

        self.main_menu = ["Audio", "Library", "Network", "System", "Display"]

        self.view = 'MAIN'
        self.idx = 0
        self.submenu_idx = 0
        self.current_category = ""
        self.current_submenu = []

        self.running = True

        # Load settings from manager
        self.invert_colors = self.settings.get('invert_colors', False)
        self.audio_output = self.settings.get('audio_output', 'Auto')

        # Sync to config globals for backward compatibility
        self.settings.sync_to_config()

        self.volume_level = 50
        self._init_volume()

        self.bt_devices = []
        self.bt_idx = 0
        self.bt_status = "Idle"

    def _save_setting(self, key: str, value):
        """Save a setting using the settings manager."""
        self.settings.set(key, value)
        self.settings.sync_to_config()

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
            self.idx = nav_index_up(self.idx, len(self.main_menu))
        elif self.view == 'SUBMENU':
            self.submenu_idx = nav_index_up(self.submenu_idx, len(self.current_submenu))
        elif self.view in ['BT_SAVED', 'BT_SCAN']:
            limit = len(self.bt_devices) + (1 if self.view == 'BT_SAVED' else 0)
            if limit > 0:
                self.bt_idx = nav_index_up(self.bt_idx, limit)

    def nav_down(self):
        if self.view == 'VOLUME':
            self._set_volume(-5)
            return
        if self.view == 'MAIN':
            self.idx = nav_index_down(self.idx, len(self.main_menu))
        elif self.view == 'SUBMENU':
            self.submenu_idx = nav_index_down(self.submenu_idx, len(self.current_submenu))
        elif self.view in ['BT_SAVED', 'BT_SCAN']:
            limit = len(self.bt_devices) + (1 if self.view == 'BT_SAVED' else 0)
            if limit > 0:
                self.bt_idx = nav_index_down(self.bt_idx, limit)

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
            ss_timeout = self.settings.get('screensaver_timeout', 60)
            ss_str = "OFF" if ss_timeout == 0 else f"{ss_timeout}s"

            self.current_submenu = [
                f"Invert Colors: {state}",
                f"Screensaver: {ss_str}"
            ]
            self.view = 'SUBMENU'

        elif category == "System":
            long_press = self.settings.get('long_press_duration', 0.5)
            self.current_submenu = [
                self._get_disk_usage(),
                f"Long Press: {long_press}s",
                "Version 1.5",
                "Restart System"
            ]
            self.view = 'SUBMENU'

    def _update_library_submenu(self):
        status = " (Scanning...)" if self.lib.is_scanning else ""
        recents_limit = self.settings.get('recents_limit', 50)
        self.current_submenu = [
            "Reload Library",
            f"Recents Limit: {recents_limit}",
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

        if cat == "AUDIO":
            if "Bluetooth" in item_text:
                self._enter_bt_saved_view()
            elif "Volume" in item_text:
                self.view = 'VOLUME'
                self._init_volume()
            elif "Output" in item_text:
                self.audio_output = self.settings.cycle('audio_output')
                self.current_submenu[self.submenu_idx] = f"Output: {self.audio_output}"

        elif cat == "LIBRARY":
            if "Reload Library" in item_text:
                self.lib.scan_async(force=True)
                self._show_popup("Rescanning...")
            elif "Recents Limit" in item_text:
                new_val = self.settings.cycle('recents_limit')
                self._update_library_submenu()

        elif cat == "DISPLAY":
            if "Invert Colors" in item_text:
                self.invert_colors = self.settings.toggle('invert_colors')
                self.current_submenu[self.submenu_idx] = f"Invert Colors: {'ON' if self.invert_colors else 'OFF'}"
            elif "Screensaver" in item_text:
                new_val = self.settings.cycle('screensaver_timeout')
                val_str = "OFF" if new_val == 0 else f"{new_val}s"
                self.current_submenu[self.submenu_idx] = f"Screensaver: {val_str}"

        elif cat == "SYSTEM":
            if "Restart" in item_text:
                subprocess.run(["sudo", "reboot"])
            elif "Long Press" in item_text:
                new_val = self.settings.cycle('long_press_duration')
                self.current_submenu[self.submenu_idx] = f"Long Press: {new_val}s"

        # Sync to config globals for backward compatibility
        self.settings.sync_to_config()

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
