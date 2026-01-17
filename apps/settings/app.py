"""
Settings application - main orchestrator for settings categories.
"""
import time
from typing import Dict, Optional

from ui.renderer import UIRenderer
from ui.menu import MenuController
from core.bluetooth import BluetoothManager
from core.settings_manager import get_settings_manager
import config as cfg

from apps.settings.categories import (
    AudioCategory, LibraryCategory, DisplayCategory,
    NetworkCategory, SystemCategory
)
from apps.base import AppBase


class SettingsApp(AppBase):
    """Main settings application."""

    def __init__(self, library_manager, audio_engine, input_handler):
        super().__init__(name="System Settings")
        self.renderer = UIRenderer()
        self.lib = library_manager
        self.audio = audio_engine
        self.bt = BluetoothManager()
        self.input = input_handler
        self.settings = get_settings_manager()

        # Initialize categories
        self._init_categories()

        # Main Menu
        self.main_menu = MenuController([
            {"name": "Audio", "type": "dir", "id": "AUDIO"},
            {"name": "Library", "type": "dir", "id": "LIBRARY"},
            {"name": "Network", "type": "dir", "id": "NETWORK"},
            {"name": "System", "type": "dir", "id": "SYSTEM"},
            {"name": "Display", "type": "dir", "id": "DISPLAY"}
        ])

        # Submenus
        self.submenu_controller = MenuController([])
        
        # View State
        self.view = 'MAIN'
        self.current_category: Optional[str] = None
        
        self.running = True

        # Load settings
        self.invert_colors = self.settings.get('invert_colors', False)
        self.settings.sync_to_config()

        # Bluetooth state
        self.bt_menu = MenuController([])
        self.bt_device_menu = MenuController([])
        self.bt_status = "Idle"
        self.bt_selected_device = None

        # WiFi state
        self.wifi_menu = MenuController([])
        self.wifi_status = "Select Network"

        # Popup state
        self.popup_msg = ""
        self.prev_view = ""
        self.popup_start = 0

    def on_enter(self):
        """Called when app is launched - reset running state."""
        self.running = True
        self.view = 'MAIN'
        self.main_menu.selected_index = 0
        self.current_category = None

    def _init_categories(self):
        """Initialize settings categories."""
        self.categories: Dict[str, object] = {
            'AUDIO': AudioCategory(self.settings, self.audio),
            'LIBRARY': LibraryCategory(self.settings, self.lib),
            'DISPLAY': DisplayCategory(self.settings),
            'NETWORK': NetworkCategory(self.settings),
            'SYSTEM': SystemCategory(self.settings)
        }
        # Link categories that need cross-references
        self.categories['SYSTEM'].set_network_category(self.categories['NETWORK'])

    def get_callbacks(self):
        return {
            'up': self.nav_up,
            'down': self.nav_down,
            'left': self.nav_left,
            'right': self.nav_right,
            'enter': self.nav_enter,
            'back': self.nav_back,
            'vol_up': lambda: self._audio_category.set_volume(5),
            'vol_down': lambda: self._audio_category.set_volume(-5)
        }

    def update(self):
        if self.view == 'SUBMENU' and self.current_category == "LIBRARY":
            # Refresh library submenu to show scan progress
            category = self.categories.get('LIBRARY')
            if category:
                category.refresh()
                self._update_submenu_items(category)
        return self.running

    def _update_submenu_items(self, category):
        """Convert category strings to dict items for MenuController."""
        # This is an adapter because categories currently return list of strings
        # We should eventually refactor categories to return dicts too, but for now wrap them.
        items = []
        info_indices = category.get_info_indices()
        for i, text in enumerate(category.items):
            item_type = 'info' if i in info_indices else 'file'
            items.append({'name': text, 'type': item_type, 'original_index': i})
        
        # Don't reset index if we are just refreshing the same list
        self.submenu_controller.set_items(items, reset_index=False)

    # --- Navigation ---
    def nav_up(self):
        if self.view == 'VOLUME':
            self._audio_category.set_volume(5)
            return
            
        if self.view == 'MAIN':
            self.main_menu.move_selection(-1)
        elif self.view == 'SUBMENU':
            self.submenu_controller.move_selection(-1)
        elif self.view in ['BT_SAVED', 'BT_SCAN']:
            self.bt_menu.move_selection(-1)
        elif self.view == 'BT_DEVICE_MENU':
            self.bt_device_menu.move_selection(-1)
        elif self.view == 'WIFI_NETWORKS':
            self.wifi_menu.move_selection(-1)

    def nav_down(self):
        if self.view == 'VOLUME':
            self._audio_category.set_volume(-5)
            return
            
        if self.view == 'MAIN':
            self.main_menu.move_selection(1)
        elif self.view == 'SUBMENU':
            self.submenu_controller.move_selection(1)
        elif self.view in ['BT_SAVED', 'BT_SCAN']:
            self.bt_menu.move_selection(1)
        elif self.view == 'BT_DEVICE_MENU':
            self.bt_device_menu.move_selection(1)
        elif self.view == 'WIFI_NETWORKS':
            self.wifi_menu.move_selection(1)

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
            item = self.main_menu.get_selected_item()
            if item:
                self._enter_category(item['id'])
                
        elif self.view == 'SUBMENU':
            self._handle_submenu_action()
            
        elif self.view == 'BT_SAVED':
            item = self.bt_menu.get_selected_item()
            if not item: return
            
            if item.get('id') == 'SCAN_NEW':
                self.view = 'BT_SCAN'
                self.bt_status = "Scanning..."
                self.bt_menu.set_items([{'name': "(Scanning...)", 'type': 'info'}])
                self.bt.start_scan(self._bt_scan_callback)
            else:
                self._enter_bt_device_menu(item['device'])
                
        elif self.view == 'BT_SCAN':
            item = self.bt_menu.get_selected_item()
            if item and item.get('device'):
                dev = item['device']
                self.bt.stop_scan()
                self.bt_status = f"Pairing {dev['name']}..."
                self.bt.connect_async(dev['mac'], self._bt_connect_callback)
                
        elif self.view == 'BT_DEVICE_MENU':
            self._handle_bt_device_action()
            
        elif self.view == 'WIFI_NETWORKS':
            item = self.wifi_menu.get_selected_item()
            if item and item.get('network'):
                network = item['network']
                self.wifi_status = "Connecting..."
                net_cat = self.categories['NETWORK']
                
                if net_cat.connect_to_wifi(network['id']):
                    # Wait briefly for connection to establish
                    time.sleep(2)
                    self.wifi_status = "Connected"
                else:
                    self.wifi_status = "Failed"
                    
                # Refresh network list and parent category
                net_cat.wifi_networks = net_cat.get_known_wifi_networks()
                net_cat.refresh()  # Refresh parent menu to show new connection

    def nav_back(self):
        if self.view == 'VOLUME':
            self.view = 'SUBMENU'
        elif self.view == 'BT_SCAN':
            self.bt.stop_scan()
            self._enter_bt_saved_view()
        elif self.view == 'BT_DEVICE_MENU':
            self._enter_bt_saved_view()
        elif self.view == 'BT_SAVED':
            self.view = 'SUBMENU'
        elif self.view == 'WIFI_NETWORKS':
            self.view = 'SUBMENU'
            self.wifi_status = "Select Network"
            # Refresh network category to show updated connection status
            self.categories['NETWORK'].refresh()
            self._update_submenu_items(self.categories['NETWORK'])
        elif self.view == 'SUBMENU':
            self.view = 'MAIN'
        elif self.view == 'MAIN':
            self.running = False
        return True

    @property
    def _audio_category(self) -> AudioCategory:
        return self.categories['AUDIO']

    def _enter_category(self, category_id: str):
        """Enter a settings category."""
        self.current_category = category_id
        
        cat_handler = self.categories.get(self.current_category)
        if cat_handler:
            cat_handler.refresh()
            self._update_submenu_items(cat_handler)
            self.submenu_controller.selected_index = 0
            self.view = 'SUBMENU'

    def _handle_submenu_action(self):
        """Handle action in current submenu."""
        item = self.submenu_controller.get_selected_item()
        if not item: return
        
        cat_handler = self.categories.get(self.current_category)
        if not cat_handler:
            return

        result = cat_handler.handle_action(item['original_index'])
        # Refresh items after action
        self._update_submenu_items(cat_handler)

        # Handle view changes
        if result == 'VOLUME':
            self.view = 'VOLUME'
        elif result == 'BT_SAVED':
            self._enter_bt_saved_view()
        elif result == 'WIFI_NETWORKS':
            self._enter_wifi_networks()

        # Sync settings to config
        self.settings.sync_to_config()
        self.invert_colors = self.settings.get('invert_colors', False)
        
    def _enter_wifi_networks(self):
        self.view = 'WIFI_NETWORKS'
        self.wifi_status = "Select Network"
        
        net_cat = self.categories['NETWORK']
        # This triggers a scan/list update in the category
        # But we need to build the menu items for MenuController
        # The category method get_known_wifi_networks returns raw dicts
        
        display_items = []
        if not net_cat.wifi_networks:
             display_items.append({'name': "(No networks)", 'type': 'info'})
        else:
            for net in net_cat.wifi_networks:
                prefix = "C" if net['current'] else " "
                display_items.append({
                    'name': f"{prefix} {net['ssid']}",
                    'type': 'file',
                    'network': net
                })
        self.wifi_menu.set_items(display_items)

    def _enter_bt_saved_view(self):
        self.view = 'BT_SAVED'
        self.bt_status = "Select Device"
        
        devices = self.bt.get_paired_devices()
        items = []
        for d in devices:
            is_conn = self.bt.is_connected(d['mac'])
            prefix = "C" if is_conn else "P"
            items.append({
                'name': f"{prefix} {d['name']}",
                'type': 'file',
                'device': d
            })
        
        items.append({'name': "[ Scan New Device ]", 'type': 'file', 'id': 'SCAN_NEW'})
        self.bt_menu.set_items(items)

    def _enter_bt_device_menu(self, device):
        """Enter device options menu."""
        self.bt_selected_device = device
        is_connected = self.bt.is_connected(device['mac'])

        options = []
        if is_connected:
            options = ["Disconnect", "Forget", "Cancel"]
        else:
            options = ["Connect", "Forget", "Cancel"]
            
        items = [{'name': opt, 'type': 'file', 'action': opt} for opt in options]
        self.bt_device_menu.set_items(items)

        self.view = 'BT_DEVICE_MENU'
        self.bt_status = device['name'][:16]

    def _handle_bt_device_action(self):
        """Handle action in BT device menu."""
        item = self.bt_device_menu.get_selected_item()
        if not item or not self.bt_selected_device:
            self._enter_bt_saved_view()
            return

        action = item['action']
        dev = self.bt_selected_device
        mac = dev['mac']

        if action == "Connect":
            self.bt_status = "Connecting..."
            self.bt.connect_async(mac, self._bt_connect_callback)
        elif action == "Disconnect":
            self.bt_status = "Disconnecting..."
            self.bt.disconnect_device(mac)
            self.bt_status = "Disconnected"
            self._enter_bt_saved_view()
        elif action == "Forget":
            self.bt_status = "Removing..."
            self.bt.forget_device(mac)
            self.bt_status = "Removed"
            self._enter_bt_saved_view()
        elif action == "Cancel":
            self._enter_bt_saved_view()

    def _show_popup(self, msg: str):
        self.popup_msg = msg
        self.prev_view = self.view
        self.view = 'POPUP'
        self.popup_start = time.time()

    def _bt_scan_callback(self, devices):
        items = []
        if not devices:
            items = [{'name': "(Scanning...)", 'type': 'info'}]
        else:
            for d in devices:
                icon = "P" if d.get('paired') else " "
                items.append({
                    'name': f"{icon} {d['name']}",
                    'type': 'file',
                    'device': d
                })
        self.bt_menu.set_items(items, reset_index=False)

    def _bt_connect_callback(self, success, msg):
        self.bt_status = msg
        if success:
            if self.view == 'BT_SCAN':
                self.bt.stop_scan()
            # Return to device list after connect attempt
            if self.view in ['BT_DEVICE_MENU', 'BT_SCAN']:
                self._enter_bt_saved_view()
                self.bt_status = msg

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
            return self.renderer.render_menu("SETTINGS", **self.main_menu.get_render_args())

        elif self.view == 'SUBMENU':
            return self.renderer.render_menu(self.current_category, **self.submenu_controller.get_render_args())

        elif self.view == 'BT_SAVED':
            return self.renderer.render_menu(f"BT: {self.bt_status}", **self.bt_menu.get_render_args())

        elif self.view == 'BT_SCAN':
            return self.renderer.render_menu(f"BT: {self.bt_status}", **self.bt_menu.get_render_args())

        elif self.view == 'BT_DEVICE_MENU':
            return self.renderer.render_menu(f"BT: {self.bt_status}", **self.bt_device_menu.get_render_args())

        elif self.view == 'WIFI_NETWORKS':
            return self.renderer.render_menu(f"WiFi: {self.wifi_status}", **self.wifi_menu.get_render_args())
            
        return self.renderer.render_menu("ERROR", ["Unknown View"], 0, 0)