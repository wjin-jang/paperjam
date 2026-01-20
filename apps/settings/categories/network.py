"""
Network settings category.

Manages network-related settings including:
- WiFi enable/disable and connection management
- Bluetooth enable/disable and status
- WiFi network scanning and password entry
"""
from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Callable

from config import setup_logger
from core.i18n import t
from ui.views.items import Item, TextInput, CHARSET_PASSWORD

from .base import SettingsCategory

if TYPE_CHECKING:
    from core.settings_manager import SettingsManager

logger = setup_logger()


class NetworkCategory(SettingsCategory):
    """Network information and configuration category.

    Handles WiFi and Bluetooth connectivity. Supports:
    - Viewing current connection status
    - Enabling/disabling radios
    - Listing and connecting to saved WiFi networks
    - Scanning for available WiFi networks
    - Adding new WiFi networks with password entry
    - Forgetting saved networks

    WiFi management uses wpa_supplicant via wpa_cli.
    Bluetooth is managed via the BluetoothManager.

    Attributes:
        bt: BluetoothManager instance.
        wifi_networks: List of known/saved WiFi networks.
        scanned_networks: List of available networks from scan.
        wifi_idx: Currently selected network index.
        password_input: TextInput for WiFi password entry.
        password_target_ssid: SSID being configured.
    """

    # WiFi connection timeout in seconds
    WIFI_TIMEOUT: int = 15

    def __init__(self, settings_manager: "SettingsManager") -> None:
        """Initialize network settings.

        Args:
            settings_manager: Reference to the app's SettingsManager.
        """
        super().__init__(t('settings.categories.network'), settings_manager)

        # Import here to avoid circular dependency
        from core.bluetooth import BluetoothManager
        self.bt = BluetoothManager()

        # WiFi state
        self.wifi_view_callback: Callable[[], None] | None = None
        self.wifi_networks: list[dict] = []
        self.scanned_networks: list[dict] = []
        self.wifi_idx: int = 0
        self._wifi_on_demand: bool = True
        self._is_scanning_wifi: bool = False

        # Password entry state
        self.password_input = TextInput(charset=CHARSET_PASSWORD)
        self.password_target_ssid: str = ""

    def set_wifi_view_callback(self, callback: Callable[[], None]) -> None:
        """Set callback to enter WiFi view.

        Args:
            callback: Function to call when entering WiFi network list.
        """
        self.wifi_view_callback = callback

    # --- WiFi Status Helpers ---

    def _is_wifi_enabled(self) -> bool:
        """Check if WiFi is enabled (not blocked by rfkill)."""
        try:
            result = subprocess.check_output(
                ["rfkill", "list", "wifi"],
                text=True, stderr=subprocess.DEVNULL, timeout=2
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

    def _get_wifi_info(self) -> str:
        """Get current WiFi connection info for display.

        Returns:
            SSID and IP if connected, status string otherwise.
        """
        if not self._is_wifi_enabled():
            return t('general.off')
        try:
            ssid = subprocess.check_output(
                ["iwgetid", "-r"],
                text=True, stderr=subprocess.DEVNULL, timeout=2
            ).strip()
            ip = subprocess.check_output(
                ['hostname', '-I'],
                encoding='utf-8', timeout=2
            ).split()[0]
            return f"{ssid} ({ip})"
        except (subprocess.SubprocessError, OSError, IndexError):
            return t('settings.network.disconnected')

    # --- WiFi Control ---

    def enable_wifi(self, timeout: int | None = None) -> bool:
        """Enable WiFi and wait for connection.

        Args:
            timeout: Max seconds to wait for connection (default: WIFI_TIMEOUT).

        Returns:
            True if connected, False if timeout or error.
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

    def disable_wifi(self) -> None:
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

    def _toggle_wifi(self) -> None:
        """Toggle WiFi on/off."""
        if self._is_wifi_enabled():
            self.disable_wifi()
        else:
            self.enable_wifi()

    # --- Bluetooth Status/Control ---

    def _is_bt_enabled(self) -> bool:
        """Check if Bluetooth is enabled."""
        try:
            result = subprocess.check_output(
                ["rfkill", "list", "bluetooth"],
                text=True, stderr=subprocess.DEVNULL, timeout=2
            )
            return "Soft blocked: no" in result
        except (subprocess.SubprocessError, OSError):
            return True

    def _toggle_bt(self) -> None:
        """Toggle Bluetooth on/off."""
        try:
            if self._is_bt_enabled():
                subprocess.run(
                    ["sudo", "rfkill", "block", "bluetooth"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
                )
            else:
                subprocess.run(
                    ["sudo", "rfkill", "unblock", "bluetooth"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
                )
        except (subprocess.SubprocessError, OSError):
            pass

    def _get_bt_status(self) -> str:
        """Get current Bluetooth status for display.

        Returns:
            Connected device name, or status string.
        """
        if not self._is_bt_enabled():
            return t('general.off')
        try:
            paired = self.bt.get_paired_devices()
            for dev in paired:
                if self.bt.is_connected(dev['mac']):
                    return dev['name']
            return t('settings.network.not_connected')
        except (subprocess.SubprocessError, OSError, KeyError):
            return t('settings.network.unavailable')

    # --- WiFi Network Management ---

    def get_known_wifi_networks(self) -> list[dict]:
        """Get list of known WiFi networks from wpa_supplicant.

        Enables WiFi if needed and fails if connection times out.

        Returns:
            List of dicts with id, ssid, current keys.
        """
        if not self._is_wifi_enabled():
            if not self.enable_wifi():
                logger.error("Failed to enable WiFi for network list")
                return []

        networks: list[dict] = []
        try:
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
        except (subprocess.SubprocessError, OSError) as e:
            logger.error(f"Failed to get WiFi networks: {e}")
        return networks

    def connect_to_wifi(self, network_id: str) -> bool:
        """Connect to a specific WiFi network by ID.

        Args:
            network_id: The wpa_supplicant network ID.

        Returns:
            True if connection successful.
        """
        if not self._is_wifi_enabled():
            if not self.enable_wifi():
                logger.error("Failed to enable WiFi for connection")
                return False

        try:
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "select_network", network_id],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
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
        except (subprocess.SubprocessError, OSError) as e:
            logger.error(f"Failed to connect to WiFi: {e}")
            return False

    def disconnect_wifi(self) -> bool:
        """Disconnect from current WiFi network."""
        try:
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "disconnect"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            logger.info("Disconnected from WiFi")
            return True
        except (subprocess.SubprocessError, OSError) as e:
            logger.error(f"Failed to disconnect WiFi: {e}")
            return False

    def forget_wifi_network(self, network_id: str) -> bool:
        """Remove a saved WiFi network.

        Args:
            network_id: The wpa_supplicant network ID to remove.

        Returns:
            True if successfully removed.
        """
        try:
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "remove_network", network_id],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "save_config"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            logger.info(f"Removed WiFi network {network_id}")
            return True
        except (subprocess.SubprocessError, OSError) as e:
            logger.error(f"Failed to remove WiFi network: {e}")
            return False

    def scan_wifi_networks(self) -> list[dict]:
        """Scan for available WiFi networks.

        Returns:
            List of dicts with ssid, signal, secured, known, flags.
        """
        if not self._is_wifi_enabled():
            if not self.enable_wifi():
                logger.error("Failed to enable WiFi for scanning")
                return []

        networks: list[dict] = []
        try:
            # Trigger a scan
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "scan"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )

            import time
            time.sleep(3)  # Wait for scan to complete

            # Get scan results
            result = subprocess.check_output(
                ["sudo", "wpa_cli", "-i", "wlan0", "scan_results"],
                text=True, stderr=subprocess.DEVNULL, timeout=5
            )

            # Parse results (skip header line)
            lines = result.strip().split('\n')[1:]
            seen_ssids: set[str] = set()

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
                    is_known = any(n['ssid'] == ssid for n in self.get_known_wifi_networks())

                    networks.append({
                        'ssid': ssid,
                        'signal': signal,
                        'secured': is_secured,
                        'known': is_known,
                        'flags': flags
                    })

            # Sort by signal strength
            networks.sort(key=lambda x: x['signal'], reverse=True)

        except (subprocess.SubprocessError, OSError) as e:
            logger.error(f"Failed to scan WiFi networks: {e}")

        self.scanned_networks = networks
        return networks

    def add_wifi_network(self, ssid: str, password: str) -> bool:
        """Add a new WiFi network with password.

        Args:
            ssid: Network SSID.
            password: Network password.

        Returns:
            True if successfully added and connected.
        """
        if not self._is_wifi_enabled():
            if not self.enable_wifi():
                return False

        try:
            # Add new network
            result = subprocess.check_output(
                ["sudo", "wpa_cli", "-i", "wlan0", "add_network"],
                text=True, stderr=subprocess.DEVNULL, timeout=5
            )
            network_id = result.strip()

            # Configure network
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "set_network", network_id, "ssid", f'"{ssid}"'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "set_network", network_id, "psk", f'"{password}"'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "enable_network", network_id],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "select_network", network_id],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
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
        except (subprocess.SubprocessError, OSError) as e:
            logger.error(f"Failed to add WiFi network: {e}")
            return False

    def add_open_wifi_network(self, ssid: str) -> bool:
        """Add an open (no password) WiFi network.

        Args:
            ssid: Network SSID.

        Returns:
            True if successfully added and connected.
        """
        if not self._is_wifi_enabled():
            if not self.enable_wifi():
                return False

        try:
            result = subprocess.check_output(
                ["sudo", "wpa_cli", "-i", "wlan0", "add_network"],
                text=True, stderr=subprocess.DEVNULL, timeout=5
            )
            network_id = result.strip()

            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "set_network", network_id, "ssid", f'"{ssid}"'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "set_network", network_id, "key_mgmt", "NONE"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "enable_network", network_id],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "select_network", network_id],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "save_config"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )

            import time
            start = time.time()
            while time.time() - start < self.WIFI_TIMEOUT:
                if self._is_wifi_connected():
                    logger.info(f"Connected to open WiFi network: {ssid}")
                    return True
                time.sleep(1)

            logger.warning(f"WiFi connection timeout for open network: {ssid}")
            return False
        except (subprocess.SubprocessError, OSError) as e:
            logger.error(f"Failed to add open WiFi network: {e}")
            return False

    # --- Password Entry Helpers ---

    def reset_password_entry(self, ssid: str = "") -> None:
        """Reset password entry state."""
        self.password_input.reset()
        self.password_target_ssid = ssid

    def get_current_password(self) -> str:
        """Get the currently entered password."""
        return self.password_input.text

    def get_current_char(self) -> str:
        """Get the currently selected character."""
        return self.password_input.current_char

    def next_char(self) -> None:
        """Move to next character in the character set."""
        self.password_input.next_char()

    def prev_char(self) -> None:
        """Move to previous character in the character set."""
        self.password_input.prev_char()

    def confirm_char(self) -> None:
        """Add current character to password."""
        self.password_input.confirm_char()

    def delete_char(self) -> None:
        """Delete last character from password."""
        self.password_input.delete_char()

    # --- Menu Building ---

    def build_menu(self) -> list[Item]:
        """Build the network settings menu."""
        wifi_info = self._get_wifi_info()
        bt_info = self._get_bt_status()
        wifi_state = t('general.on') if self._is_wifi_enabled() else t('general.off')
        bt_state = t('general.on') if self._is_bt_enabled() else t('general.off')
        return [
            Item(columns=[t('settings.network.wifi'), wifi_info], selectable=False),
            Item(columns=[t('settings.network.bluetooth'), bt_info], selectable=False),
            Item(columns=[t('settings.network.toggle_wifi'), wifi_state], selectable=True),
            Item(text=t('settings.network.wifi_networks')),
            Item(columns=[t('settings.network.toggle_bt'), bt_state], selectable=True)
        ]

    def handle_action(self, item_index: int) -> str | None:
        """Handle network settings menu selection."""
        item = self.items[item_index]
        item_text = item.columns[0] if item.columns else item.text

        if t('settings.network.toggle_wifi') in item_text:
            self._toggle_wifi()
            self.refresh()
        elif t('settings.network.wifi_networks') in item_text:
            self.wifi_networks = self.get_known_wifi_networks()
            self.wifi_idx = 0
            return 'WIFI_NETWORKS'
        elif t('settings.network.toggle_bt') in item_text:
            self._toggle_bt()
            self.refresh()

        return None
