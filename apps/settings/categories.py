"""
Settings category handlers for modular settings management.
"""
import re
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Callable

import config as cfg
import version
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

    def get_info_indices(self) -> List[int]:
        """Return indices of info-only items that should not be selectable."""
        return []

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
        self._mixer_control = self._find_mixer_control()
        self._init_volume()
        self._refresh_audio_sinks()

    def _find_mixer_control(self) -> str:
        """Find an available mixer control name."""
        # Common control names in order of preference
        controls = ['Master', 'PCM', 'Speaker', 'Headphone', 'Digital']
        try:
            # Get list of available controls
            result = subprocess.check_output(
                ["amixer", "scontrols"],
                text=True, stderr=subprocess.DEVNULL, timeout=2
            )
            for ctrl in controls:
                if f"'{ctrl}'" in result:
                    return ctrl
            # If none found, try to extract first available
            if "Simple mixer control" in result:
                # Extract name between quotes
                import re
                match = re.search(r"'([^']+)'", result)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return 'Master'  # Default fallback

    def _init_volume(self):
        try:
            # Avoid shell=True to prevent shell injection
            result = subprocess.check_output(
                ["amixer", "get", self._mixer_control],
                text=True, stderr=subprocess.DEVNULL, timeout=2
            )
            # Parse percentage from output
            match = re.search(r'\[(\d+)%\]', result)
            if match:
                self.volume_level = int(match.group(1))
            else:
                self.volume_level = 50
        except (subprocess.SubprocessError, ValueError, OSError):
            self.volume_level = 50

    def _refresh_audio_sinks(self):
        """Get list of available PulseAudio sinks (audio output devices)."""
        self._audio_sinks = []
        try:
            # Get full sink info including descriptions
            result = subprocess.check_output(
                ["pactl", "list", "sinks"],
                text=True, stderr=subprocess.DEVNULL, timeout=2
            )

            current_sink = {}
            for line in result.split('\n'):
                line = line.strip()
                if line.startswith('Sink #'):
                    if current_sink.get('name'):
                        self._audio_sinks.append(current_sink)
                    current_sink = {'id': line.split('#')[1]}
                elif line.startswith('Name:'):
                    current_sink['name'] = line.split(':', 1)[1].strip()
                elif line.startswith('Description:'):
                    desc = line.split(':', 1)[1].strip()
                    # Truncate long descriptions
                    current_sink['display'] = desc[:20] if len(desc) > 20 else desc

            # Don't forget the last sink
            if current_sink.get('name'):
                self._audio_sinks.append(current_sink)

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
            # PulseAudio not available, add a default entry
            self._audio_sinks = [{'id': '0', 'name': 'default', 'display': 'Default'}]
            self._current_sink_index = 0

    def _get_current_output_name(self) -> str:
        """Get the display name of the current audio output."""
        if self._audio_sinks and 0 <= self._current_sink_index < len(self._audio_sinks):
            return self._audio_sinks[self._current_sink_index]['display']
        return "None"

    def _cycle_audio_output(self) -> str:
        """Cycle to the next audio output device."""
        self._refresh_audio_sinks()
        if not self._audio_sinks:
            return "None"
        if len(self._audio_sinks) == 1:
            return self._audio_sinks[0]['display']

        # Cycle to next sink
        self._current_sink_index = (self._current_sink_index + 1) % len(self._audio_sinks)
        sink = self._audio_sinks[self._current_sink_index]

        # Set as default sink (only if PulseAudio is available)
        if sink['name'] != 'default':
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
            subprocess.run(
                ["amixer", "set", self._mixer_control, f"{self.volume_level}%"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
            )
        except (subprocess.SubprocessError, OSError):
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
        elif item_text.startswith("Output:"):
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

    def build_menu(self) -> List[str]:
        recents_limit = self.settings.get('recents_limit', 50)

        if self.lib.is_scanning:
            # Show scan progress
            return [
                f"Scanning: {self.lib.scan_current_file}",
                f"Tracks: {self.lib.scan_track_count}",
                f"Albums: {self.lib.scan_album_count}",
                f"Artists: {self.lib.scan_artist_count}",
                f"Recents Limit: {recents_limit}"
            ]
        else:
            # Show library stats
            tracks = self.lib.get_total_tracks()
            albums = len(self.lib.albums)
            artists = len(self.lib.artists)
            return [
                f"Tracks: {tracks}",
                f"Albums: {albums}",
                f"Artists: {artists}",
                "Rescan Library",
                f"Recents Limit: {recents_limit}"
            ]

    def get_info_indices(self) -> List[int]:
        if self.lib.is_scanning:
            return [0, 1, 2, 3]  # All scan info is info-only
        else:
            return [0, 1, 2]  # Stats are info-only

    def handle_action(self, item_index: int) -> Optional[str]:
        item_text = self.items[item_index]

        if "Rescan Library" in item_text:
            self.lib.scan_async(force=True)
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
                ["tvservice", "-s"], text=True, stderr=subprocess.DEVNULL, timeout=2
            ).strip()
            # "state 0x120006" means off, other states mean on
            return "off" not in result.lower() and "0x120006" not in result
        except (subprocess.SubprocessError, OSError):
            return True

    def _toggle_hdmi(self):
        """Toggle HDMI output on/off."""
        try:
            if self._is_hdmi_enabled():
                subprocess.run(["tvservice", "-o"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            else:
                subprocess.run(["tvservice", "-p"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                # Restore framebuffer after turning on
                subprocess.run(["fbset", "-depth", "8"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                subprocess.run(["fbset", "-depth", "16"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        except (subprocess.SubprocessError, OSError):
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
                ["rfkill", "list", "wifi"], text=True, stderr=subprocess.DEVNULL, timeout=2
            )
            return "Soft blocked: no" in result
        except (subprocess.SubprocessError, OSError):
            return True

    def _toggle_wifi(self):
        """Toggle WiFi on/off."""
        try:
            if self._is_wifi_enabled():
                subprocess.run(["sudo", "rfkill", "block", "wifi"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            else:
                subprocess.run(["sudo", "rfkill", "unblock", "wifi"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                # Bring interface up and reconnect
                subprocess.run(["sudo", "ifconfig", "wlan0", "up"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                subprocess.run(["sudo", "wpa_cli", "-i", "wlan0", "reconnect"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        except (subprocess.SubprocessError, OSError):
            pass

    def _is_bt_enabled(self) -> bool:
        """Check if Bluetooth is enabled."""
        try:
            result = subprocess.check_output(
                ["rfkill", "list", "bluetooth"], text=True, stderr=subprocess.DEVNULL, timeout=2
            )
            return "Soft blocked: no" in result
        except (subprocess.SubprocessError, OSError):
            return True

    def _toggle_bt(self):
        """Toggle Bluetooth on/off."""
        try:
            if self._is_bt_enabled():
                subprocess.run(["sudo", "rfkill", "block", "bluetooth"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            else:
                subprocess.run(["sudo", "rfkill", "unblock", "bluetooth"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        except (subprocess.SubprocessError, OSError):
            pass

    def _get_wifi_info(self) -> str:
        if not self._is_wifi_enabled():
            return "OFF"
        try:
            ssid = subprocess.check_output(
                ["iwgetid", "-r"], text=True, stderr=subprocess.DEVNULL, timeout=2
            ).strip()
            ip = subprocess.check_output(
                ['hostname', '-I'], encoding='utf-8', timeout=2
            ).split()[0]
            return f"{ssid} ({ip})"
        except (subprocess.SubprocessError, OSError, IndexError):
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
        except (subprocess.SubprocessError, OSError, KeyError):
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
        wifi_info = self._get_wifi_info()
        bt_info = self._get_bt_status()
        return [
            f"WiFi: {wifi_info}",
            f"Bluetooth: {bt_info}",
            f"Toggle WiFi: {wifi_state}",
            "WiFi Networks",
            f"Toggle BT: {bt_state}"
        ]

    def get_info_indices(self) -> List[int]:
        return [0, 1]  # WiFi info and BT status at top are info-only

    def handle_action(self, item_index: int) -> Optional[str]:
        item_text = self.items[item_index]

        if item_text.startswith("Toggle WiFi"):
            self._toggle_wifi()
            self.refresh()
        elif "WiFi Networks" in item_text:
            self.wifi_networks = self.get_known_wifi_networks()
            self.wifi_idx = 0
            return 'WIFI_NETWORKS'
        elif item_text.startswith("Toggle BT"):
            self._toggle_bt()
            self.refresh()
        return None


class SystemCategory(SettingsCategory):
    """System settings category."""

    def __init__(self, settings_manager):
        super().__init__("SYSTEM", settings_manager)
        self._screen_clear_callback = None
        self._update_callback = None
        self._update_status = ""

    def set_screen_clear_callback(self, callback):
        """Set callback for screen clear shutdown."""
        self._screen_clear_callback = callback

    def set_update_callback(self, callback):
        """Set callback for performing updates."""
        self._update_callback = callback

    def _get_disk_usage(self) -> str:
        try:
            # Avoid shell=True - use Python to parse
            result = subprocess.check_output(
                ["df", "-h", "/"], text=True, timeout=2
            )
            # Parse the output: second line, fourth column
            lines = result.strip().split('\n')
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 4:
                    return parts[3] + " Free"
            return "Unknown"
        except (subprocess.SubprocessError, OSError, IndexError):
            return "Unknown"

    def _get_cpu_governor(self) -> str:
        """Get current CPU governor."""
        try:
            # Read file directly instead of using cat subprocess
            governor_path = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
            with open(governor_path, 'r') as f:
                return f.read().strip()
        except (OSError, IOError):
            return "unknown"

    def _toggle_cpu_powersave(self):
        """Toggle between performance and powersave CPU governors."""
        try:
            current = self._get_cpu_governor()
            if current == "powersave":
                new_gov = "ondemand"
            else:
                new_gov = "powersave"
            # Set governor for all CPUs using sudo tee
            # Shell is needed here for glob pattern, but new_gov is controlled
            subprocess.run(
                ["sudo", "tee"] + list(Path("/sys/devices/system/cpu/").glob("cpu*/cpufreq/scaling_governor")),
                input=new_gov, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
        except (subprocess.SubprocessError, OSError):
            pass

    def build_menu(self) -> List[str]:
        long_press = self.settings.get('long_press_duration', 0.5)
        auto_update = self.settings.get('auto_update', False)
        auto_update_str = "ON" if auto_update else "OFF"
        cpu_gov = self._get_cpu_governor()
        cpu_mode = "Powersave" if cpu_gov == "powersave" else "Normal"
        disk = self._get_disk_usage()
        return [
            f"Disk: {disk}",
            f"Ver: {version.VERSION} ({version.VERSION_DATE})",
            f"CPU Mode: {cpu_mode}",
            f"Long Press: {long_press}s",
            f"Auto-Update: {auto_update_str}",
            "Check for Updates",
            "Restart System",
            "Clear Screen + Shut Down"
        ]

    def get_info_indices(self) -> List[int]:
        return [0, 1]  # Disk and Version lines are info-only

    def handle_action(self, item_index: int) -> Optional[str]:
        item_text = self.items[item_index]

        if "CPU Mode" in item_text:
            self._toggle_cpu_powersave()
            self.refresh()
        elif "Auto-Update" in item_text:
            new_val = self.settings.toggle('auto_update')
            state = "ON" if new_val else "OFF"
            self.items[item_index] = f"Auto-Update: {state}"
        elif "Check for Updates" in item_text:
            if self._update_callback:
                self._update_callback()
        elif "Restart" in item_text:
            subprocess.run(["sudo", "reboot"], timeout=5)
        elif "Long Press" in item_text:
            new_val = self.settings.cycle('long_press_duration')
            self.items[item_index] = f"Long Press: {new_val}s"
        elif "Clear Screen" in item_text:
            if self._screen_clear_callback:
                self._screen_clear_callback()

        return None
