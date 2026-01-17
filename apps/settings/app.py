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
        super().__init__(name=t('menu.settings'))
        self.renderer = UIRenderer()
        self.lib = library_manager
        self.audio = audio_engine
        self.bt = BluetoothManager()
        self.input = input_handler
        self.settings = get_settings_manager()

        # Initialize categories
        self._init_categories()

        # Main Menu
        from ui.views.items import Item
        self.main_menu = MenuController([
            Item(text=t('settings.categories.audio'), type='text', id="AUDIO"),
            Item(text=t('settings.categories.library'), type='text', id="LIBRARY"),
            Item(text=t('settings.categories.network'), type='text', id="NETWORK"),
            Item(text=t('settings.categories.system'), type='text', id="SYSTEM"),
            Item(text=t('settings.categories.display'), type='text', id="DISPLAY")
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
        self.bt_status = t('settings.bluetooth.idle')
        self.bt_selected_device = None

        # WiFi state
        self.wifi_menu = MenuController([])
        self.wifi_status = t('settings.network.select_network')

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
        """Convert category items to dict items for MenuController."""
        from ui.views.items import Item
        items = []
        for i, item_data in enumerate(category.items):
            if isinstance(item_data, Item):
                # We can pass the Item object directly to MenuController now
                items.append(item_data)
                # We still need to map the index for handle_action if needed, 
                # but MenuController stores the list as is.
            else:
                # Fallback for any legacy items
                items.append({'name': str(item_data), 'type': 'text', 'original_index': i})
        
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
                self._enter_category(item.id)
                
        elif self.view == 'SUBMENU':
            self._handle_submenu_action()
            
        elif self.view == 'BT_SAVED':
            item = self.bt_menu.get_selected_item()
            if not item: return
            
            if item.id == 'SCAN_NEW':
                self.view = 'BT_SCAN'
                self.bt_status = t('settings.bluetooth.scanning')
                from ui.views.items import Item
                self.bt_menu.set_items([Item(text=t('settings.bluetooth.scanning'), type='info', selectable=False)])
                self.bt.start_scan(self._bt_scan_callback)
            else:
                self._enter_bt_device_menu(item.id) # id stores device dict
                
        elif self.view == 'BT_SCAN':
            item = self.bt_menu.get_selected_item()
            if item and item.id: # id stores device dict
                dev = item.id
                self.bt.stop_scan()
                self.bt_status = t('settings.bluetooth.pairing')
                self.bt.connect_async(dev['mac'], self._bt_connect_callback)
                
        elif self.view == 'BT_DEVICE_MENU':
            self._handle_bt_device_action()
            
        elif self.view == 'WIFI_NETWORKS':
            item = self.wifi_menu.get_selected_item()
            if item and item.id: # id stores network dict
                network = item.id
                self.wifi_status = t('settings.network.connecting')
                net_cat = self.categories['NETWORK']
                
                if net_cat.connect_to_wifi(network['id']):
                    # Wait briefly for connection to establish
                    time.sleep(2)
                    self.wifi_status = t('settings.network.connected')
                else:
                    self.wifi_status = t('settings.network.failed')
                    
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
            self.wifi_status = t('settings.network.select_network')
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
        sel_idx = self.submenu_controller.selected_index
        item = self.submenu_controller.get_selected_item()
        if not item: return
        
        cat_handler = self.categories.get(self.current_category)
        if not cat_handler:
            return

        result = cat_handler.handle_action(sel_idx)
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
        self.wifi_status = t('settings.network.select_network')
        
        net_cat = self.categories['NETWORK']
        from ui.views.items import Item
        
        display_items = []
        if not net_cat.wifi_networks:
             display_items.append(Item(text=t('settings.network.no_networks'), type='info', selectable=False))
        else:
            for net in net_cat.wifi_networks:
                prefix = "C" if net['current'] else " "
                display_items.append(Item(
                    text=f"{prefix} {net['ssid']}",
                    type='text',
                    id=net
                ))
        self.wifi_menu.set_items(display_items)

    def _enter_bt_saved_view(self):
        self.view = 'BT_SAVED'
        self.bt_status = t('settings.bluetooth.select_device')
        
        from ui.views.items import Item
        devices = self.bt.get_paired_devices()
        items = []
        for d in devices:
            is_conn = self.bt.is_connected(d['mac'])
            prefix = "C" if is_conn else "P"
            items.append(Item(
                text=f"{prefix} {d['name']}",
                type='text',
                id=d
            ))
        
        items.append(Item(text=t('settings.bluetooth.scan_new'), type='text', id='SCAN_NEW'))
        self.bt_menu.set_items(items)

    def _enter_bt_device_menu(self, device):
        """Enter device options menu."""
        from ui.views.items import Item
        self.bt_selected_device = device
        is_connected = self.bt.is_connected(device['mac'])

        options = []
        if is_connected:
            options = [
                t('settings.bluetooth.disconnect'),
                t('settings.bluetooth.forget_short'),
                t('general.cancel')
            ]
        else:
            options = [
                t('settings.bluetooth.connect'),
                t('settings.bluetooth.forget_short'),
                t('general.cancel')
            ]
            
        items = [Item(text=opt, type='text', id=opt) for opt in options]
        self.bt_device_menu.set_items(items)

        self.view = 'BT_DEVICE_MENU'
        self.bt_status = device['name'][:16]

    def _handle_bt_device_action(self):
        """Handle action in BT device menu."""
        item = self.bt_device_menu.get_selected_item()
        if not item or not self.bt_selected_device:
            self._enter_bt_saved_view()
            return

        action = item.id
        dev = self.bt_selected_device
        mac = dev['mac']

        if action == t('settings.bluetooth.connect'):
            self.bt_status = t('settings.bluetooth.connecting')
            self.bt.connect_async(mac, self._bt_connect_callback)
        elif action == t('settings.bluetooth.disconnect'):
            self.bt_status = t('settings.bluetooth.disconnecting')
            self.bt.disconnect_device(mac)
            self.bt_status = t('settings.bluetooth.idle') # Or disconnected?
            self._enter_bt_saved_view()
        elif action == t('settings.bluetooth.forget_short'):
            self.bt_status = t('settings.bluetooth.forgetting')
            self.bt.forget_device(mac)
            self.bt_status = t('settings.bluetooth.removed')
            self._enter_bt_saved_view()
        elif action == t('general.cancel'):
            self._enter_bt_saved_view()

...

    def _bt_scan_callback(self, devices):
        from ui.views.items import Item
        items = []
        if not devices:
            items = [Item(text=t('settings.bluetooth.scanning'), type='info', selectable=False)]
        else:
            for d in devices:
                icon = "P" if d.get('paired') else " "
                items.append(Item(
                    text=f"{icon} {d['name']}",
                    type='text',
                    id=d
                ))
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
            return self.renderer.render_volume(t('general.volume_popup'), self._audio_category.volume_level)

        if self.view == 'POPUP':
            is_busy = self.lib.is_scanning or (time.time() - self.popup_start < 1.5)
            if not is_busy:
                self.view = self.prev_view
            else:
                frame, _ = self.renderer.render_menu(t('general.please_wait'), [Item(text=self.popup_msg, type='info')], 0, 0)
                return frame

        if self.view == 'MAIN':
            frame, scroll = self.renderer.render_menu(t('settings.title'), **self.main_menu.get_render_args())
            self.main_menu.scroll_offset = scroll
            return frame

        elif self.view == 'SUBMENU':
            frame, scroll = self.renderer.render_menu(self.current_category, **self.submenu_controller.get_render_args())
            self.submenu_controller.scroll_offset = scroll
            return frame

        elif self.view == 'BT_SAVED':
            frame, scroll = self.renderer.render_menu(t('settings.bluetooth.title', status=self.bt_status), **self.bt_menu.get_render_args())
            self.bt_menu.scroll_offset = scroll
            return frame

        elif self.view == 'BT_SCAN':
            frame, scroll = self.renderer.render_menu(t('settings.bluetooth.title', status=self.bt_status), **self.bt_menu.get_render_args())
            self.bt_menu.scroll_offset = scroll
            return frame

        elif self.view == 'BT_DEVICE_MENU':
            frame, scroll = self.renderer.render_menu(t('settings.bluetooth.title', status=self.bt_status), **self.bt_device_menu.get_render_args())
            self.bt_device_menu.scroll_offset = scroll
            return frame

        elif self.view == 'WIFI_NETWORKS':
            frame, scroll = self.renderer.render_menu(t('settings.network.title', status=self.wifi_status), **self.wifi_menu.get_render_args())
            self.wifi_menu.scroll_offset = scroll
            return frame
            
        frame, _ = self.renderer.render_menu(t('general.error'), [Item(text=t('general.unknown_view'), type='info')], 0, 0)
        return frame