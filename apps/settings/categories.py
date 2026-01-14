"""
Settings category handlers for modular settings management.
"""
import subprocess
from abc import ABC, abstractmethod
from typing import List, Optional, Callable

import config as cfg


class SettingsCategory(ABC):
    """Abstract base class for settings categories."""

    def __init__(self, name: str, settings_manager):
        self.name = name
        self.settings = settings_manager
        self.items: List[str] = []

    @abstractmethod
    def build_menu(self) -> List[str]:
        """Build and return the menu items for this category."""
        pass

    @abstractmethod
    def handle_action(self, item_index: int) -> Optional[str]:
        """
        Handle action for selected item.

        Returns:
            View to switch to, or None to stay in submenu
        """
        pass

    def refresh(self):
        """Refresh the menu items."""
        self.items = self.build_menu()


class AudioCategory(SettingsCategory):
    """Audio settings category."""

    def __init__(self, settings_manager, audio_engine):
        super().__init__("AUDIO", settings_manager)
        self.audio = audio_engine
        self.volume_level = 50
        self._init_volume()

    def _init_volume(self):
        try:
            cmd = "amixer get Master | grep -o '[0-9]*%' | head -1"
            res = subprocess.check_output(cmd, shell=True, text=True).strip().replace('%', '')
            self.volume_level = int(res)
        except:
            self.volume_level = 50

    def set_volume(self, change: int):
        self.volume_level = max(0, min(100, self.volume_level + change))
        try:
            subprocess.run(["amixer", "set", "Master", f"{self.volume_level}%"], stdout=subprocess.DEVNULL)
        except:
            pass

    def build_menu(self) -> List[str]:
        audio_output = self.settings.get('audio_output', 'Auto')
        return [
            f"Output: {audio_output}",
            "Volume",
            "Bluetooth Manager"
        ]

    def handle_action(self, item_index: int) -> Optional[str]:
        item_text = self.items[item_index]

        if "Bluetooth" in item_text:
            return 'BT_SAVED'
        elif "Volume" in item_text:
            self._init_volume()
            return 'VOLUME'
        elif "Output" in item_text:
            new_val = self.settings.cycle('audio_output')
            self.items[item_index] = f"Output: {new_val}"
            return None

        return None


class LibraryCategory(SettingsCategory):
    """Library settings category."""

    def __init__(self, settings_manager, library_manager):
        super().__init__("LIBRARY", settings_manager)
        self.lib = library_manager
        self._show_popup: Optional[Callable] = None

    def set_popup_handler(self, handler: Callable):
        self._show_popup = handler

    def build_menu(self) -> List[str]:
        status = " (Scanning...)" if self.lib.is_scanning else ""
        recents_limit = self.settings.get('recents_limit', 50)
        return [
            "Reload Library",
            f"Recents Limit: {recents_limit}",
            f"Tracks: {self.lib.get_total_tracks()}{status}",
            f"Albums: {len(self.lib.albums)}",
            f"Artists: {len(self.lib.artists)}"
        ]

    def handle_action(self, item_index: int) -> Optional[str]:
        item_text = self.items[item_index]

        if "Reload Library" in item_text:
            self.lib.scan_async(force=True)
            if self._show_popup:
                self._show_popup("Rescanning...")
        elif "Recents Limit" in item_text:
            self.settings.cycle('recents_limit')
            self.refresh()

        return None


class DisplayCategory(SettingsCategory):
    """Display settings category."""

    def __init__(self, settings_manager):
        super().__init__("DISPLAY", settings_manager)

    def build_menu(self) -> List[str]:
        invert = self.settings.get('invert_colors', False)
        state = "ON" if invert else "OFF"
        ss_timeout = self.settings.get('screensaver_timeout', 60)
        ss_str = "OFF" if ss_timeout == 0 else f"{ss_timeout}s"

        return [
            f"Invert Colors: {state}",
            f"Screensaver: {ss_str}"
        ]

    def handle_action(self, item_index: int) -> Optional[str]:
        item_text = self.items[item_index]

        if "Invert Colors" in item_text:
            new_val = self.settings.toggle('invert_colors')
            self.items[item_index] = f"Invert Colors: {'ON' if new_val else 'OFF'}"
        elif "Screensaver" in item_text:
            new_val = self.settings.cycle('screensaver_timeout')
            val_str = "OFF" if new_val == 0 else f"{new_val}s"
            self.items[item_index] = f"Screensaver: {val_str}"

        return None


class NetworkCategory(SettingsCategory):
    """Network information category."""

    def __init__(self, settings_manager):
        super().__init__("NETWORK", settings_manager)

    def _get_wifi_info(self) -> str:
        try:
            ssid = subprocess.check_output("iwgetid -r", shell=True, text=True).strip()
            ip = subprocess.check_output(['hostname', '-I'], encoding='utf-8').split()[0]
            return f"{ssid} ({ip})"
        except:
            return "Disconnected"

    def build_menu(self) -> List[str]:
        return [
            f"WiFi: {self._get_wifi_info()}",
            "Bluetooth Status"
        ]

    def handle_action(self, item_index: int) -> Optional[str]:
        # Network category is informational only
        return None


class SystemCategory(SettingsCategory):
    """System settings category."""

    def __init__(self, settings_manager):
        super().__init__("SYSTEM", settings_manager)

    def _get_disk_usage(self) -> str:
        try:
            return subprocess.check_output(
                "df -h / | grep / | awk '{print $4}'",
                shell=True, text=True
            ).strip() + " Free"
        except:
            return "Unknown"

    def build_menu(self) -> List[str]:
        long_press = self.settings.get('long_press_duration', 0.5)
        return [
            self._get_disk_usage(),
            f"Long Press: {long_press}s",
            "Version 1.5",
            "Restart System"
        ]

    def handle_action(self, item_index: int) -> Optional[str]:
        item_text = self.items[item_index]

        if "Restart" in item_text:
            subprocess.run(["sudo", "reboot"])
        elif "Long Press" in item_text:
            new_val = self.settings.cycle('long_press_duration')
            self.items[item_index] = f"Long Press: {new_val}s"

        return None
