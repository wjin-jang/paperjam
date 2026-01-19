"""
Settings category handlers for modular settings management.
"""
import json
import re
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Callable, Any

import config as cfg
from core.settings_manager import format_duration
from config import setup_logger
from core.i18n import t
from ui.views.items import Item

logger = setup_logger()


class SettingsCategory(ABC):
    """Abstract base class for settings categories."""

    def __init__(self, name: str, settings_manager):
        self.name = name
        self.settings = settings_manager
        self.items: List[Item] = []

    @abstractmethod
    def build_menu(self) -> List[Item]:
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
        return [i for i, item in enumerate(self.items) if not item.selectable]

    def refresh(self):
        """Refresh the menu items."""
        self.items = self.build_menu()


class AudioCategory(SettingsCategory):
    """Audio settings category."""

    def __init__(self, settings_manager, audio_engine):
        super().__init__(t('settings.categories.audio'), settings_manager)
        self.audio = audio_engine
        self.volume_level = cfg.DEFAULT_VOLUME
        self._audio_sinks = []
        self._current_sink_index = 0
        self._mixer_control = self._find_mixer_control()
        self._load_volume()
        self._refresh_audio_sinks()

    def _load_volume(self):
        """Load volume from persistent storage or use default."""
        try:
            if cfg.VOLUME_FILE.exists():
                with open(cfg.VOLUME_FILE, 'r') as f:
                    data = json.load(f)
                    self.volume_level = data.get('volume', cfg.DEFAULT_VOLUME)
                    # Apply the loaded volume to system
                    self._apply_volume()
                    logger.info(f"Volume loaded: {self.volume_level}%")
                    return
        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.warning(f"Failed to load volume: {e}")

        # Use default and apply it
        self.volume_level = cfg.DEFAULT_VOLUME
        self._apply_volume()

    def save_volume(self):
        """Save current volume to persistent storage."""
        try:
            with open(cfg.VOLUME_FILE, 'w') as f:
                json.dump({'volume': self.volume_level}, f)
            logger.info(f"Volume saved: {self.volume_level}%")
        except OSError as e:
            logger.error(f"Failed to save volume: {e}")

    def _apply_volume(self):
        """Apply volume to all audio outputs (ALSA + PulseAudio)."""
        try:
            # Set ALSA mixer
            subprocess.run(
                ["amixer", "set", self._mixer_control, f"{self.volume_level}%"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
            )
        except (subprocess.SubprocessError, OSError) as e:
            logger.warning(f"Failed to set ALSA volume: {e}")

        try:
            # Set PulseAudio sink volume
            subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{self.volume_level}%"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
            )
        except (subprocess.SubprocessError, OSError) as e:
            logger.warning(f"Failed to set PulseAudio volume: {e}")

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
        except Exception as e:
            logger.warning(f"Failed to find mixer control: {e}")
        return 'Master'  # Default fallback

    def _read_system_volume(self):
        """Read current system volume (for display only, not for initialization)."""
        try:
            result = subprocess.check_output(
                ["amixer", "get", self._mixer_control],
                text=True, stderr=subprocess.DEVNULL, timeout=2
            )
            match = re.search(r'\[(\d+)%\]', result)
            if match:
                return int(match.group(1))
        except (subprocess.SubprocessError, ValueError, OSError) as e:
            logger.debug(f"Failed to read system volume: {e}")
        return self.volume_level

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
        except Exception as e:
            logger.warning(f"PulseAudio sinks not available: {e}")
            # PulseAudio not available, add a default entry
            self._audio_sinks = [{'id': '0', 'name': 'default', 'display': t('general.default')}]
            self._current_sink_index = 0

    def _get_current_output_name(self) -> str:
        """Get the display name of the current audio output."""
        if self._audio_sinks and 0 <= self._current_sink_index < len(self._audio_sinks):
            return self._audio_sinks[self._current_sink_index]['display']
        return t('settings.bluetooth.none')

    def _cycle_audio_output(self) -> str:
        """Cycle to the next audio output device."""
        self._refresh_audio_sinks()
        if not self._audio_sinks:
            return t('settings.bluetooth.none')
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
            except Exception as e:
                logger.warning(f"Failed to set default sink: {e}")

        return sink['display']

    def set_volume(self, change: int):
        """Change volume by given amount and persist."""
        self.volume_level = max(0, min(100, self.volume_level + change))
        self._apply_volume()
        self.save_volume()

    def build_menu(self) -> List[Item]:
        self._refresh_audio_sinks()
        output_name = self._get_current_output_name()
        endless = self.settings.get('endless_playback', False)
        endless_state = t('general.on') if endless else t('general.off')
        return [
            Item(columns=[t('settings.audio.output'), output_name], selectable=True),
            Item(text=t('settings.audio.volume')),
            Item(columns=[t('settings.audio.endless_play'), endless_state], selectable=True),
            Item(text=t('settings.audio.bluetooth'))
        ]

    def handle_action(self, item_index: int) -> Optional[str]:
        item = self.items[item_index]
        item_text = item.columns[0] if item.columns else item.text

        if t('settings.audio.bluetooth') in item_text:
            return 'BT_SAVED'
        elif t('settings.audio.volume') in item_text:
            return 'VOLUME'
        elif t('settings.audio.output') in item_text:
            new_output = self._cycle_audio_output()
            return None
        elif t('settings.audio.endless_play') in item_text:
            self.settings.toggle('endless_playback')
            self.refresh()
            return None

        return None


class LibraryCategory(SettingsCategory):
    """Library settings category."""

    def __init__(self, settings_manager, library_manager):
        super().__init__(t('settings.categories.library'), settings_manager)
        self.lib = library_manager

    def build_menu(self) -> List[Item]:
        recents_limit = self.settings.get('recents_limit', 50)

        if self.lib.is_scanning:
            # Show scan progress
            return [
                Item(columns=[t('settings.library.scanning'), self.lib.scan_current_file], selectable=False),
                Item(columns=[t('settings.library.tracks'), str(self.lib.scan_track_count)], selectable=False),
                Item(columns=[t('settings.library.albums'), str(self.lib.scan_album_count)], selectable=False),
                Item(columns=[t('settings.library.artists'), str(self.lib.scan_artist_count)], selectable=False),
                Item(columns=[t('settings.library.recents_limit'), str(recents_limit)], selectable=False)
            ]
        else:
            # Show library stats
            tracks = self.lib.get_total_tracks()
            albums = len(self.lib.albums)
            artists = len(self.lib.artists)
            return [
                Item(columns=[t('settings.library.tracks'), str(tracks)], selectable=False),
                Item(columns=[t('settings.library.albums'), str(albums)], selectable=False),
                Item(columns=[t('settings.library.artists'), str(artists)], selectable=False),
                Item(text=t('settings.library.rescan')),
                Item(columns=[t('settings.library.recents_limit'), str(recents_limit)], selectable=True)
            ]

    def handle_action(self, item_index: int) -> Optional[str]:
        item = self.items[item_index]
        item_text = item.columns[0] if item.columns else item.text

        if t('settings.library.rescan') in item_text:
            self.lib.scan_async(force=True)
        elif t('settings.library.recents_limit') in item_text:
            self.settings.cycle('recents_limit')
            self.refresh()

        return None


class DisplayCategory(SettingsCategory):
    """Display settings category."""

    def __init__(self, settings_manager):
        super().__init__(t('settings.categories.display'), settings_manager)

    def build_menu(self) -> List[Item]:
        invert = self.settings.get('invert_colors', False)
        state = t('general.on') if invert else t('general.off')
        ss_timeout = self.settings.get('screensaver_timeout', 60)

        return [
            Item(columns=[t('settings.display.invert_colors'), state], selectable=True),
            Item(columns=[t('settings.display.screensaver'), format_duration(ss_timeout)], selectable=True)
        ]

    def handle_action(self, item_index: int) -> Optional[str]:
        item = self.items[item_index]
        item_text = item.columns[0] if item.columns else item.text

        if t('settings.display.invert_colors') in item_text:
            self.settings.toggle('invert_colors')
            self.refresh()
        elif t('settings.display.screensaver') in item_text:
            self.settings.cycle('screensaver_timeout')
            self.refresh()

        return None


class NetworkCategory(SettingsCategory):
    """Network information category."""

    # WiFi connection timeout in seconds
    WIFI_TIMEOUT = 15

    # Character set for password entry (a-z, A-Z, 0-9, common symbols)
    PASSWORD_CHARS = (
        list('abcdefghijklmnopqrstuvwxyz') +
        list('ABCDEFGHIJKLMNOPQRSTUVWXYZ') +
        list('0123456789') +
        list('!@#$%^&*()-_=+[]{}|;:,.<>?/~` ')
    )

    def __init__(self, settings_manager):
        super().__init__(t('settings.categories.network'), settings_manager)
        from core.bluetooth import BluetoothManager
        self.bt = BluetoothManager()
        self.wifi_view_callback = None
        self.wifi_networks = []  # Known/saved networks
        self.scanned_networks = []  # Available networks from scan
        self.wifi_idx = 0
        self._wifi_on_demand = True  # Enable WiFi on-demand by default
        self._is_scanning_wifi = False

        # Password entry state
        self.password_chars = []  # List of characters entered
        self.password_char_idx = 0  # Current character in PASSWORD_CHARS
        self.password_target_ssid = ""  # SSID we're entering password for

    def set_wifi_view_callback(self, callback):
        """Set callback to enter WiFi view."""
        self.wifi_view_callback = callback

    def _is_wifi_enabled(self) -> bool:
        """Check if WiFi is enabled (not blocked)."""
        try:
            result = subprocess.check_output(
                ["rfkill", "list", "wifi"], text=True, stderr=subprocess.DEVNULL, timeout=2
            )
            return "Soft blocked: no" in result
        except (subprocess.SubprocessError, OSError):
            return True

    def _is_wifi_connected(self) -> bool:
        """Check if WiFi is connected with an IP address."""
        try:
            result = subprocess.check_output(
                ["ip", "-4", "addr", "show", "wlan0"],
                text=True, stderr=subprocess.DEVNULL, timeout=2
            )
            return "inet " in result
        except (subprocess.SubprocessError, OSError):
            return False

    def enable_wifi(self, timeout: int = None) -> bool:
        """
        Enable WiFi and wait for connection.

        Args:
            timeout: Max seconds to wait for connection (default: WIFI_TIMEOUT)

        Returns:
            True if connected, False if timeout or error
        """
        if timeout is None:
            timeout = self.WIFI_TIMEOUT

        try:
            # Unblock WiFi
            subprocess.run(
                ["sudo", "rfkill", "unblock", "wifi"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )

            # Bring interface up
            subprocess.run(
                ["sudo", "ip", "link", "set", "wlan0", "up"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )

            # Tell wpa_supplicant to reconnect
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "reconnect"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )

            # Wait for connection
            import time
            start = time.time()
            while time.time() - start < timeout:
                if self._is_wifi_connected():
                    logger.info("WiFi enabled and connected")
                    return True
                time.sleep(1)

            logger.warning(f"WiFi enable timeout after {timeout}s")
            return False
        except (subprocess.SubprocessError, OSError) as e:
            logger.error(f"Failed to enable WiFi: {e}")
            return False

    def disable_wifi(self):
        """Disable WiFi to save power."""
        try:
            subprocess.run(
                ["sudo", "ip", "link", "set", "wlan0", "down"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            subprocess.run(
                ["sudo", "rfkill", "block", "wifi"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            logger.info("WiFi disabled")
        except (subprocess.SubprocessError, OSError) as e:
            logger.error(f"Failed to disable WiFi: {e}")

    def _toggle_wifi(self):
        """Toggle WiFi on/off."""
        if self._is_wifi_enabled():
            self.disable_wifi()
        else:
            self.enable_wifi()

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
            return t('general.off')
        try:
            ssid = subprocess.check_output(
                ["iwgetid", "-r"], text=True, stderr=subprocess.DEVNULL, timeout=2
            ).strip()
            ip = subprocess.check_output(
                ['hostname', '-I'], encoding='utf-8', timeout=2
            ).split()[0]
            return f"{ssid} ({ip})"
        except (subprocess.SubprocessError, OSError, IndexError):
            return t('settings.network.disconnected')

    def _get_bt_status(self) -> str:
        if not self._is_bt_enabled():
            return t('general.off')
        try:
            paired = self.bt.get_paired_devices()
            for dev in paired:
                if self.bt.is_connected(dev['mac']):
                    return dev['name'][:16]
            return t('settings.network.not_connected')
        except (subprocess.SubprocessError, OSError, KeyError):
            return t('settings.network.unavailable')

    def get_known_wifi_networks(self) -> List[dict]:
        """Get list of known WiFi networks from wpa_supplicant.

        Enables WiFi if needed and fails if connection times out.
        """
        # Enable WiFi if not enabled
        if not self._is_wifi_enabled():
            if not self.enable_wifi():
                logger.error("Failed to enable WiFi for network list")
                return []

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
                if len(parts) >= 2:
                    network_id = parts[0]
                    ssid = parts[1]
                    flags = parts[3] if len(parts) > 3 else ""
                    is_current = "CURRENT" in flags
                    networks.append({
                        'id': network_id,
                        'ssid': ssid,
                        'current': is_current
                    })
        except Exception as e:
            logger.error(f"Failed to get WiFi networks: {e}")
        return networks

    def connect_to_wifi(self, network_id: str) -> bool:
        """Connect to a specific WiFi network by ID.

        Enables WiFi if needed and waits for connection.
        Returns False if connection fails.
        """
        # Enable WiFi if not enabled
        if not self._is_wifi_enabled():
            if not self.enable_wifi():
                logger.error("Failed to enable WiFi for connection")
                return False

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

            # Wait for connection
            import time
            start = time.time()
            while time.time() - start < self.WIFI_TIMEOUT:
                if self._is_wifi_connected():
                    logger.info(f"Connected to WiFi network {network_id}")
                    return True
                time.sleep(1)

            logger.warning(f"WiFi connection timeout for network {network_id}")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to WiFi: {e}")
            return False

    def scan_wifi_networks(self) -> List[dict]:
        """Scan for available WiFi networks.

        Returns list of networks with ssid, signal, security info.
        """
        # Enable WiFi if not enabled
        if not self._is_wifi_enabled():
            if not self.enable_wifi():
                logger.error("Failed to enable WiFi for scanning")
                return []

        networks = []
        try:
            # Trigger a scan
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "scan"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )

            # Wait for scan to complete
            import time
            time.sleep(3)

            # Get scan results
            result = subprocess.check_output(
                ["sudo", "wpa_cli", "-i", "wlan0", "scan_results"],
                text=True, stderr=subprocess.DEVNULL, timeout=5
            )

            # Parse results (skip header line)
            # Format: bssid / frequency / signal level / flags / ssid
            lines = result.strip().split('\n')[1:]
            seen_ssids = set()

            for line in lines:
                parts = line.split('\t')
                if len(parts) >= 5:
                    ssid = parts[4].strip()
                    if not ssid or ssid in seen_ssids:
                        continue
                    seen_ssids.add(ssid)

                    signal = int(parts[2]) if parts[2].lstrip('-').isdigit() else -100
                    flags = parts[3]
                    is_secured = 'WPA' in flags or 'WEP' in flags

                    # Check if this network is already known
                    is_known = any(n['ssid'] == ssid for n in self.get_known_wifi_networks())

                    networks.append({
                        'ssid': ssid,
                        'signal': signal,
                        'secured': is_secured,
                        'known': is_known,
                        'flags': flags
                    })

            # Sort by signal strength (strongest first)
            networks.sort(key=lambda x: x['signal'], reverse=True)

        except Exception as e:
            logger.error(f"Failed to scan WiFi networks: {e}")

        self.scanned_networks = networks
        return networks

    def add_wifi_network(self, ssid: str, password: str) -> bool:
        """Add a new WiFi network with password.

        Returns True if successfully added and connected.
        """
        # Enable WiFi if not enabled
        if not self._is_wifi_enabled():
            if not self.enable_wifi():
                logger.error("Failed to enable WiFi for adding network")
                return False

        try:
            # Add new network and get its ID
            result = subprocess.check_output(
                ["sudo", "wpa_cli", "-i", "wlan0", "add_network"],
                text=True, stderr=subprocess.DEVNULL, timeout=5
            )
            network_id = result.strip()

            # Set SSID
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "set_network", network_id, "ssid", f'"{ssid}"'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )

            # Set password (PSK)
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "set_network", network_id, "psk", f'"{password}"'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )

            # Enable the network
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "enable_network", network_id],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )

            # Select and connect to network
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "select_network", network_id],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )

            # Save configuration
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "save_config"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )

            # Wait for connection
            import time
            start = time.time()
            while time.time() - start < self.WIFI_TIMEOUT:
                if self._is_wifi_connected():
                    logger.info(f"Connected to new WiFi network: {ssid}")
                    return True
                time.sleep(1)

            logger.warning(f"WiFi connection timeout for new network: {ssid}")
            return False

        except Exception as e:
            logger.error(f"Failed to add WiFi network: {e}")
            return False

    def add_open_wifi_network(self, ssid: str) -> bool:
        """Add an open (no password) WiFi network.

        Returns True if successfully added and connected.
        """
        # Enable WiFi if not enabled
        if not self._is_wifi_enabled():
            if not self.enable_wifi():
                logger.error("Failed to enable WiFi for adding network")
                return False

        try:
            # Add new network and get its ID
            result = subprocess.check_output(
                ["sudo", "wpa_cli", "-i", "wlan0", "add_network"],
                text=True, stderr=subprocess.DEVNULL, timeout=5
            )
            network_id = result.strip()

            # Set SSID
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "set_network", network_id, "ssid", f'"{ssid}"'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )

            # Set key management to NONE for open networks
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "set_network", network_id, "key_mgmt", "NONE"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )

            # Enable the network
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "enable_network", network_id],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )

            # Select and connect to network
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "select_network", network_id],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )

            # Save configuration
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "save_config"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )

            # Wait for connection
            import time
            start = time.time()
            while time.time() - start < self.WIFI_TIMEOUT:
                if self._is_wifi_connected():
                    logger.info(f"Connected to open WiFi network: {ssid}")
                    return True
                time.sleep(1)

            logger.warning(f"WiFi connection timeout for open network: {ssid}")
            return False

        except Exception as e:
            logger.error(f"Failed to add open WiFi network: {e}")
            return False

    # Password entry helpers
    def reset_password_entry(self, ssid: str = ""):
        """Reset password entry state."""
        self.password_chars = []
        self.password_char_idx = 0
        self.password_target_ssid = ssid

    def get_current_password(self) -> str:
        """Get the currently entered password."""
        return ''.join(self.password_chars)

    def get_current_char(self) -> str:
        """Get the currently selected character."""
        return self.PASSWORD_CHARS[self.password_char_idx]

    def next_char(self):
        """Move to next character in the character set."""
        self.password_char_idx = (self.password_char_idx + 1) % len(self.PASSWORD_CHARS)

    def prev_char(self):
        """Move to previous character in the character set."""
        self.password_char_idx = (self.password_char_idx - 1) % len(self.PASSWORD_CHARS)

    def confirm_char(self):
        """Add current character to password."""
        self.password_chars.append(self.PASSWORD_CHARS[self.password_char_idx])
        self.password_char_idx = 0  # Reset to 'a'

    def delete_char(self):
        """Delete last character from password."""
        if self.password_chars:
            self.password_chars.pop()

    def build_menu(self) -> List[Item]:
        wifi_info = self._get_wifi_info()
        bt_info = self._get_bt_status()
        wifi_state = t('general.on') if self._is_wifi_enabled() else t('general.off')
        bt_state = t('general.on') if self._is_bt_enabled() else t('general.off')
        return [
            Item(columns=[t('settings.network.wifi'), wifi_info], selectable=False),
            Item(columns=[t('settings.network.bluetooth'), bt_info], selectable=False),
            Item(columns=[t('settings.network.toggle_wifi'), wifi_state], selectable=True),
            Item(text=t('settings.network.wifi_networks')),
            Item(text=t('settings.network.scan_wifi')),
            Item(columns=[t('settings.network.toggle_bt'), bt_state], selectable=True)
        ]

    def handle_action(self, item_index: int) -> Optional[str]:
        item = self.items[item_index]
        item_text = item.columns[0] if item.columns else item.text

        if t('settings.network.toggle_wifi') in item_text:
            self._toggle_wifi()
            self.refresh()
        elif t('settings.network.wifi_networks') in item_text:
            self.wifi_networks = self.get_known_wifi_networks()
            self.wifi_idx = 0
            return 'WIFI_NETWORKS'
        elif t('settings.network.scan_wifi') in item_text:
            return 'WIFI_SCAN'
        elif t('settings.network.toggle_bt') in item_text:
            self._toggle_bt()
            self.refresh()
        return None


class SystemCategory(SettingsCategory):
    """System settings category."""

    # Path to power optimization script
    POWER_SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "power_optimise.sh"

    def __init__(self, settings_manager):
        super().__init__(t('settings.categories.system'), settings_manager)
        self._screen_clear_callback = None
        self._update_callback = None
        self._reset_callback = None
        self._update_status = ""
        self._network_category = None  # Set by SettingsApp for WiFi control

    def set_network_category(self, network_cat):
        """Set reference to NetworkCategory for WiFi control."""
        self._network_category = network_cat

    def set_screen_clear_callback(self, callback):
        """Set callback for screen clear shutdown."""
        self._screen_clear_callback = callback

    def set_update_callback(self, callback):
        """Set callback for performing updates."""
        self._update_callback = callback

    def set_reset_callback(self, callback):
        """Set callback for reset data action."""
        self._reset_callback = callback

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
                    return f"{parts[3]} {t('settings.system.free')}"
            return t('settings.system.unknown')
        except (subprocess.SubprocessError, OSError, IndexError) as e:
            logger.warning(f"Failed to get disk usage: {e}")
            return t('settings.system.unknown')

    def _get_cpu_governor(self) -> str:
        """Get current CPU governor."""
        try:
            governor_path = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
            with open(governor_path, 'r') as f:
                return f.read().strip()
        except (OSError, IOError):
            return "unknown"

    def _is_power_optimised(self) -> bool:
        """Check if power optimizations are enabled."""
        return self._get_cpu_governor() == "powersave"

    def _toggle_power_mode(self):
        """Toggle between optimised and normal power modes."""
        try:
            if self._is_power_optimised():
                # Disable optimizations
                if self.POWER_SCRIPT.exists():
                    subprocess.run(
                        ["sudo", "bash", str(self.POWER_SCRIPT), "disable"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10
                    )
                else:
                    # Fallback: just set governor
                    self._set_cpu_governor("ondemand")
                logger.info("Power optimizations disabled")
            else:
                # Enable optimizations
                if self.POWER_SCRIPT.exists():
                    subprocess.run(
                        ["sudo", "bash", str(self.POWER_SCRIPT), "enable"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10
                    )
                else:
                    # Fallback: just set governor
                    self._set_cpu_governor("powersave")

                # Disable WiFi as part of power optimization
                if self._network_category:
                    self._network_category.disable_wifi()

                logger.info("Power optimizations enabled")
        except (subprocess.SubprocessError, OSError) as e:
            logger.error(f"Failed to toggle power mode: {e}")

    def _set_cpu_governor(self, governor: str):
        """Set CPU governor for all CPUs.

        For 'normal' mode, tries governors in order: ondemand, schedutil, performance.
        For 'powersave' mode, uses powersave directly.
        """
        try:
            for cpu_path in Path("/sys/devices/system/cpu/").glob("cpu*/cpufreq/scaling_governor"):
                avail_path = cpu_path.parent / "scaling_available_governors"

                # For normal mode, try multiple governors
                if governor == "ondemand":
                    governors_to_try = ["ondemand", "schedutil", "performance"]
                else:
                    governors_to_try = [governor]

                for gov in governors_to_try:
                    # Check if governor is available
                    try:
                        avail = avail_path.read_text()
                        if gov not in avail:
                            continue
                    except OSError:
                        pass  # Try anyway

                    result = subprocess.run(
                        ["sudo", "tee", str(cpu_path)],
                        input=gov, text=True,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
                    )
                    if result.returncode == 0:
                        break  # Success, move to next CPU
        except (subprocess.SubprocessError, OSError):
            pass

    def build_menu(self) -> List[Item]:
        long_press = self.settings.get('long_press_duration', 0.5)
        auto_update = self.settings.get('auto_update', False)
        auto_update_str = t('general.on') if auto_update else t('general.off')
        power_mode = t('settings.system.power_optimised') if self._is_power_optimised() else t('settings.system.power_normal')
        disk = self._get_disk_usage()
        return [
            Item(columns=[t('settings.system.disk'), disk], selectable=False),
            Item(columns=[t('settings.system.version'), f"{cfg.VERSION} ({cfg.VERSION_DATE})"], selectable=False),
            Item(columns=[t('settings.system.power_mode'), power_mode], selectable=True),
            Item(columns=[t('settings.system.long_press'), f"{long_press}s"], selectable=True),
            Item(columns=[t('settings.system.auto_update'), auto_update_str], selectable=True),
            Item(text=t('settings.system.check_updates')),
            Item(text=t('settings.system.restart')),
            Item(text=t('settings.system.reset_data')),
            Item(text=t('settings.system.shutdown'))
        ]

    def handle_action(self, item_index: int) -> Optional[str]:
        item = self.items[item_index]
        item_text = item.columns[0] if item.columns else item.text

        if t('settings.system.power_mode') in item_text:
            self._toggle_power_mode()
            self.refresh()
        elif t('settings.system.auto_update') in item_text:
            self.settings.toggle('auto_update')
            self.refresh()
        elif t('settings.system.check_updates') in item_text:
            if self._update_callback:
                self._update_callback()
        elif t('settings.system.restart') in item_text:
            subprocess.run(["sudo", "reboot"], timeout=5)
        elif t('settings.system.long_press') in item_text:
            self.settings.cycle('long_press_duration')
            self.refresh()
        elif t('settings.system.reset_data') in item_text:
            if self._reset_callback:
                self._reset_callback()
        elif t('settings.system.shutdown') in item_text:
            if self._screen_clear_callback:
                self._screen_clear_callback()

        return None
