"""
Settings application - main orchestrator for settings categories.
"""
import time
from typing import Dict, Optional

from ui.renderer import UIRenderer
from core.bluetooth import BluetoothManager
from core.navigation import nav_index_up, nav_index_down
from core.settings_manager import get_settings_manager
import config as cfg

from apps.settings.categories import (
    AudioCategory, LibraryCategory, DisplayCategory,
    NetworkCategory, SystemCategory
)


class SettingsApp:
    """Main settings application."""

    def __init__(self, library_manager, audio_engine, input_handler):
        self.renderer = UIRenderer()
        self.lib = library_manager
        self.audio = audio_engine
        self.bt = BluetoothManager()
        self.input = input_handler
        self.settings = get_settings_manager()

        # Initialize categories
        self._init_categories()

        self.main_menu = ["Audio", "Library", "Network", "System", "Display"]

        self.view = 'MAIN'
        self.idx = 0
        self.submenu_idx = 0
        self.current_category: Optional[str] = None
        self.current_submenu = []

        self.running = True

        # Load settings
        self.invert_colors = self.settings.get('invert_colors', False)
        self.settings.sync_to_config()

        # Bluetooth state
        self.bt_devices = []
        self.bt_idx = 0
        self.bt_status = "Idle"

        # Popup state
        self.popup_msg = ""
        self.prev_view = ""
        self.popup_start = 0

    def _init_categories(self):
        """Initialize settings categories."""
        self.categories: Dict[str, object] = {
            'AUDIO': AudioCategory(self.settings, self.audio),
            'LIBRARY': LibraryCategory(self.settings, self.lib),
            'DISPLAY': DisplayCategory(self.settings),
            'NETWORK': NetworkCategory(self.settings),
            'SYSTEM': SystemCategory(self.settings)
        }
        # Set popup handler for library category
        self.categories['LIBRARY'].set_popup_handler(self._show_popup)

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
            # Refresh library submenu to show scan progress
            category = self.categories.get('LIBRARY')
            if category:
                category.refresh()
                self.current_submenu = category.items
        return self.running

    # --- Navigation ---
    def nav_up(self):
        if self.view == 'VOLUME':
            self._audio_category.set_volume(5)
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
            self._audio_category.set_volume(-5)
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
        if self.view == 'VOLUME':
            self._audio_category.set_volume(-5)

    def nav_right(self):
        if self.view == 'VOLUME':
            self._audio_category.set_volume(5)

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

    @property
    def _audio_category(self) -> AudioCategory:
        return self.categories['AUDIO']

    def _enter_category(self, category: str):
        """Enter a settings category."""
        self.current_category = category.upper()
        self.submenu_idx = 0

        cat_handler = self.categories.get(self.current_category)
        if cat_handler:
            cat_handler.refresh()
            self.current_submenu = cat_handler.items
            self.view = 'SUBMENU'

    def _handle_submenu_action(self):
        """Handle action in current submenu."""
        cat_handler = self.categories.get(self.current_category)
        if not cat_handler:
            return

        result = cat_handler.handle_action(self.submenu_idx)
        self.current_submenu = cat_handler.items

        # Handle view changes
        if result == 'VOLUME':
            self.view = 'VOLUME'
        elif result == 'BT_SAVED':
            self._enter_bt_saved_view()

        # Sync settings to config
        self.settings.sync_to_config()
        self.invert_colors = self.settings.get('invert_colors', False)

    def _enter_bt_saved_view(self):
        self.view = 'BT_SAVED'
        self.bt_status = "Select Device"
        self.bt_devices = self.bt.get_paired_devices()
        self.bt_idx = 0

    def _show_popup(self, msg: str):
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
            return self.renderer.render_volume("VOLUME", self._audio_category.volume_level)

        if self.view == 'POPUP':
            is_busy = self.lib.is_scanning or (time.time() - self.popup_start < 1.5)
            if not is_busy:
                self.view = self.prev_view
            else:
                return self.renderer.render_menu("PLEASE WAIT", [self.popup_msg], 0, 0)

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
            if not self.bt_devices:
                display_list = ["(Scanning...)"]
            else:
                display_list = []
                for d in self.bt_devices:
                    icon = "P" if d.get('paired') else " "
                    display_list.append(f"{icon} {d['name']}")
            return self.renderer.render_menu(f"BT: {self.bt_status}", display_list, self.bt_idx, 0)
