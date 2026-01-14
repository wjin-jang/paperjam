"""
Settings category handlers for modular settings management.
"""
import subprocess
from abc import ABC, abstractmethod
from typing import List, Optional, Callable

import config as cfg
from core.settings_manager import format_duration


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
        self._audio_sinks = []
        self._current_sink_index = 0
        self._init_volume()
        self._refresh_audio_sinks()

    def _init_volume(self):
        try:
            cmd = "amixer get Master | grep -o '[0-9]*%' | head -1"
            res = subprocess.check_output(cmd, shell=True, text=True).strip().replace('%', '')
            self.volume_level = int(res)
        except:
            self.volume_level = 50

    def _refresh_audio_sinks(self):
        """Get list of available PulseAudio sinks (audio output devices)."""
        self._audio_sinks = []
        try:
            result = subprocess.check_output(
                ["pactl", "list", "short", "sinks"],
                text=True, stderr=subprocess.DEVNULL, timeout=2
            )
            for line in result.strip().split('\n'):
                if line:
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        sink_id = parts[0]
                        sink_name = parts[1]
                        # Create a friendly display name
                        if 'bluez' in sink_name.lower():
                            display = 'Bluetooth'
                        elif 'hdmi' in sink_name.lower():
                            display = 'HDMI'
                        elif 'usb' in sink_name.lower():
                            display = 'USB'
                        elif 'headphone' in sink_name.lower():
                            display = 'Headphones'
                        else:
                            # Use last part of name for display
                            display = sink_name.split('.')[-1][:12]
                        self._audio_sinks.append({
                            'id': sink_id,
                            'name': sink_name,
                            'display': display
                        })
            # Find current default sink
            default = subprocess.check_output(
                ["pactl", "get-default-sink"],
                text=True, stderr=subprocess.DEVNULL, timeout=2
            ).strip()
            for i, sink in enumerate(self._audio_sinks):
                if sink['name'] == default:
                    self._current_sink_index = i
                    break
        except Exception:
            pass

    def _get_current_output_name(self) -> str:
        """Get the display name of the current audio output."""
        if self._audio_sinks and 0 <= self._current_sink_index < len(self._audio_sinks):
            return self._audio_sinks[self._current_sink_index]['display']
        return "Default"

    def _cycle_audio_output(self) -> str:
        """Cycle to the next audio output device."""
        self._refresh_audio_sinks()
        if not self._audio_sinks:
            return "No Devices"

        # Cycle to next sink
        self._current_sink_index = (self._current_sink_index + 1) % len(self._audio_sinks)
        sink = self._audio_sinks[self._current_sink_index]

        # Set as default sink
        try:
            subprocess.run(
                ["pactl", "set-default-sink", sink['name']],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
            )
            # Move currently playing streams to new sink
            subprocess.run(
                f"pactl list short sink-inputs | cut -f1 | xargs -I{{}} pactl move-sink-input {{}} {sink['name']}",
                shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
            )
        except Exception:
            pass

        return sink['display']

    def set_volume(self, change: int):
        self.volume_level = max(0, min(100, self.volume_level + change))
        try:
            subprocess.run(["amixer", "set", "Master", f"{self.volume_level}%"], stdout=subprocess.DEVNULL)
        except:
            pass

    def build_menu(self) -> List[str]:
        self._refresh_audio_sinks()
        output_name = self._get_current_output_name()
        endless = self.settings.get('endless_playback', False)
        endless_state = "ON" if endless else "OFF"
        return [
            f"Output: {output_name}",
            "Volume",
            f"Endless Play: {endless_state}",
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
            new_output = self._cycle_audio_output()
            self.items[item_index] = f"Output: {new_output}"
            return None
        elif "Endless" in item_text:
            new_val = self.settings.toggle('endless_playback')
            self.items[item_index] = f"Endless Play: {'ON' if new_val else 'OFF'}"
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

    def _is_hdmi_enabled(self) -> bool:
        """Check if HDMI output is enabled."""
        try:
            result = subprocess.check_output(
                ["tvservice", "-s"], text=True, stderr=subprocess.DEVNULL
            ).strip()
            # "state 0x120006" means off, other states mean on
            return "off" not in result.lower() and "0x120006" not in result
        except:
            return True

    def _toggle_hdmi(self):
        """Toggle HDMI output on/off."""
        try:
            if self._is_hdmi_enabled():
                subprocess.run(["tvservice", "-o"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["tvservice", "-p"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # Restore framebuffer after turning on
                subprocess.run(["fbset", "-depth", "8"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["fbset", "-depth", "16"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            pass

    def build_menu(self) -> List[str]:
        invert = self.settings.get('invert_colors', False)
        state = "ON" if invert else "OFF"
        ss_timeout = self.settings.get('screensaver_timeout', 60)
        hdmi_state = "ON" if self._is_hdmi_enabled() else "OFF"

        return [
            f"Invert Colors: {state}",
            f"Screensaver: {format_duration(ss_timeout)}",
            f"HDMI Output: {hdmi_state}"
        ]

    def handle_action(self, item_index: int) -> Optional[str]:
        item_text = self.items[item_index]

        if "Invert Colors" in item_text:
            new_val = self.settings.toggle('invert_colors')
            self.items[item_index] = f"Invert Colors: {'ON' if new_val else 'OFF'}"
        elif "Screensaver" in item_text:
            new_val = self.settings.cycle('screensaver_timeout')
            self.items[item_index] = f"Screensaver: {format_duration(new_val)}"
        elif "HDMI" in item_text:
            self._toggle_hdmi()
            self.refresh()

        return None


class NetworkCategory(SettingsCategory):
    """Network information category."""

    def __init__(self, settings_manager):
        super().__init__("NETWORK", settings_manager)
        from core.bluetooth import BluetoothManager
        self.bt = BluetoothManager()
        self.wifi_view_callback = None
        self.wifi_networks = []
        self.wifi_idx = 0

    def set_wifi_view_callback(self, callback):
        """Set callback to enter WiFi view."""
        self.wifi_view_callback = callback

    def _is_wifi_enabled(self) -> bool:
        """Check if WiFi is enabled."""
        try:
            result = subprocess.check_output(
                ["rfkill", "list", "wifi"], text=True, stderr=subprocess.DEVNULL
            )
            return "Soft blocked: no" in result
        except:
            return True

    def _toggle_wifi(self):
        """Toggle WiFi on/off."""
        try:
            if self._is_wifi_enabled():
                subprocess.run(["sudo", "rfkill", "block", "wifi"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["sudo", "rfkill", "unblock", "wifi"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # Bring interface up and reconnect
                subprocess.run(["sudo", "ifconfig", "wlan0", "up"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["sudo", "wpa_cli", "-i", "wlan0", "reconnect"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            pass

    def _is_bt_enabled(self) -> bool:
        """Check if Bluetooth is enabled."""
        try:
            result = subprocess.check_output(
                ["rfkill", "list", "bluetooth"], text=True, stderr=subprocess.DEVNULL
            )
            return "Soft blocked: no" in result
        except:
            return True

    def _toggle_bt(self):
        """Toggle Bluetooth on/off."""
        try:
            if self._is_bt_enabled():
                subprocess.run(["sudo", "rfkill", "block", "bluetooth"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["sudo", "rfkill", "unblock", "bluetooth"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            pass

    def _get_wifi_info(self) -> str:
        if not self._is_wifi_enabled():
            return "OFF"
        try:
            ssid = subprocess.check_output("iwgetid -r", shell=True, text=True).strip()
            ip = subprocess.check_output(['hostname', '-I'], encoding='utf-8').split()[0]
            return f"{ssid} ({ip})"
        except:
            return "Disconnected"

    def _get_bt_status(self) -> str:
        if not self._is_bt_enabled():
            return "OFF"
        try:
            paired = self.bt.get_paired_devices()
            for dev in paired:
                if self.bt.is_connected(dev['mac']):
                    return dev['name'][:16]
            return "Not Connected"
        except:
            return "Unavailable"

    def get_known_wifi_networks(self) -> List[dict]:
        """Get list of known WiFi networks from wpa_supplicant."""
        networks = []
        try:
            # Get list of configured networks from wpa_cli
            result = subprocess.check_output(
                ["sudo", "wpa_cli", "-i", "wlan0", "list_networks"],
                text=True, stderr=subprocess.DEVNULL, timeout=5
            )
            # Skip header line and parse rest
            lines = result.strip().split('\n')[1:]
            for line in lines:
                parts = line.split('\t')
                if len(parts) >= 4:
                    network_id = parts[0]
                    ssid = parts[1]
                    flags = parts[3] if len(parts) > 3 else ""
                    is_current = "CURRENT" in flags
                    networks.append({
                        'id': network_id,
                        'ssid': ssid,
                        'current': is_current
                    })
        except Exception:
            pass
        return networks

    def connect_to_wifi(self, network_id: str) -> bool:
        """Connect to a specific WiFi network by ID."""
        try:
            # Select the network
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "select_network", network_id],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            # Force reconnection
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "reconnect"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            return True
        except Exception:
            return False

    def build_menu(self) -> List[str]:
        wifi_state = "ON" if self._is_wifi_enabled() else "OFF"
        bt_state = "ON" if self._is_bt_enabled() else "OFF"
        return [
            f"WiFi: {wifi_state}",
            f"  {self._get_wifi_info()}",
            "WiFi Networks",
            f"Bluetooth: {bt_state}",
            f"  {self._get_bt_status()}"
        ]

    def handle_action(self, item_index: int) -> Optional[str]:
        if item_index == 0:
            self._toggle_wifi()
            self.refresh()
        elif item_index == 2:
            # WiFi Networks menu
            self.wifi_networks = self.get_known_wifi_networks()
            self.wifi_idx = 0
            return 'WIFI_NETWORKS'
        elif item_index == 3:
            self._toggle_bt()
            self.refresh()
        return None


class SystemCategory(SettingsCategory):
    """System settings category."""

    def __init__(self, settings_manager):
        super().__init__("SYSTEM", settings_manager)
        self._screen_clear_callback = None

    def set_screen_clear_callback(self, callback):
        """Set callback for screen clear shutdown."""
        self._screen_clear_callback = callback

    def _get_disk_usage(self) -> str:
        try:
            return subprocess.check_output(
                "df -h / | grep / | awk '{print $4}'",
                shell=True, text=True
            ).strip() + " Free"
        except:
            return "Unknown"

    def _get_cpu_governor(self) -> str:
        """Get current CPU governor."""
        try:
            result = subprocess.check_output(
                ["cat", "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"],
                text=True, stderr=subprocess.DEVNULL
            ).strip()
            return result
        except:
            return "unknown"

    def _toggle_cpu_powersave(self):
        """Toggle between performance and powersave CPU governors."""
        try:
            current = self._get_cpu_governor()
            if current == "powersave":
                new_gov = "ondemand"
            else:
                new_gov = "powersave"
            # Set governor for all CPUs
            subprocess.run(
                f"echo {new_gov} | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor",
                shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except:
            pass

    def build_menu(self) -> List[str]:
        long_press = self.settings.get('long_press_duration', 0.5)
        cpu_gov = self._get_cpu_governor()
        cpu_mode = "Powersave" if cpu_gov == "powersave" else "Normal"
        return [
            f"CPU Mode: {cpu_mode}",
            self._get_disk_usage(),
            f"Long Press: {long_press}s",
            f"Version {cfg.VERSION}",
            "Restart System",
            "Clear Screen + Shut Down"
        ]

    def handle_action(self, item_index: int) -> Optional[str]:
        item_text = self.items[item_index]

        if "CPU Mode" in item_text:
            self._toggle_cpu_powersave()
            self.refresh()
        elif "Restart" in item_text:
            subprocess.run(["sudo", "reboot"])
        elif "Long Press" in item_text:
            new_val = self.settings.cycle('long_press_duration')
            self.items[item_index] = f"Long Press: {new_val}s"
        elif "Clear Screen" in item_text:
            if self._screen_clear_callback:
                self._screen_clear_callback()

        return None
