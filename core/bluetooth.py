"""
Bluetooth device management via bluetoothctl.

Features:
- Device scanning and discovery
- Pairing, connecting, disconnecting
- Saved device management
- Audio output routing to Bluetooth devices

Uses subprocess to interact with bluetoothctl for compatibility
with systems that don't have DBus Python bindings installed.
"""
import subprocess
import time
import threading
import re
import shlex
from core.logger import setup_logger

logger = setup_logger()


class BluetoothManager:
    def __init__(self):
        self.scan_process = None
        self.found_devices = {} 
        self._lock = threading.Lock()
        self.is_scanning = False
        
        # Filter noise from logs
        self.ignore_keywords = [
            "RSSI", "TxPower", "ManufacturerData", "ServiceData", "AdvertisingData",
            "AddressType", "Class", "Icon", "UUID", "Modalias", "Appearance",
            "Connected", "Bonded", "Paired", "LegacyPairing", "Trusted", "Blocked",
            "Controller", "[CHG]", "[NEW]", "[DEL]", "Transport", "Simulated",
            "Type", "Alias", "Discoverable", "Pairable", "Power", "Advertisingflags",
            "light", "Agent", "registered", "Default", "agent", "RequestConfirmation",
            "Authorize", "Passkey", "PIN", "org.bluez", "SetDiscoveryFilter",
            "Discovery", "started", "stopped", "Attempting", "Request", "successful",
            "failed", "error", "yes", "no"
        ]

        # Regex pattern for valid MAC address
        self.mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')

    def _run_cmd(self, cmd):
        try:
            return subprocess.check_output(cmd, encoding='utf-8', stderr=subprocess.DEVNULL)
        except Exception:
            return ""

    def _clean_ansi(self, text):
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def _is_valid_mac(self, mac):
        """Check if string is a valid MAC address."""
        return bool(self.mac_pattern.match(mac))

    def _is_valid_device_name(self, name):
        """Check if a name is a valid device name (not a bluetoothctl message)."""
        if not name or len(name) < 2:
            return False
        # Filter keywords
        if any(x.lower() in name.lower() for x in self.ignore_keywords):
            return False
        # Filter names that look like status messages
        if name.startswith('[') or name.endswith(']'):
            return False
        if ':' in name and len(name.split(':')) > 2:
            # Might be a MAC address or path, not a name
            return False
        return True

    def is_connected(self, mac):
        """Checks if a specific device is currently connected."""
        if not self._is_valid_mac(mac):
            return False
        info = self._run_cmd(['bluetoothctl', 'info', mac])
        return "Connected: yes" in info

    def _is_audio_device(self, mac):
        """Check if a device is an audio device based on its icon/class."""
        if not self._is_valid_mac(mac):
            return False
        info = self._run_cmd(['bluetoothctl', 'info', mac])
        # Check for audio-related icons
        audio_icons = ['audio-headset', 'audio-headphones', 'audio-card', 'audio-speakers']
        for line in info.split('\n'):
            if 'Icon:' in line:
                icon = line.split('Icon:')[1].strip().lower()
                if any(ai in icon for ai in audio_icons):
                    return True
            # Also check Class for audio device class codes (0x04 = Audio/Video)
            if 'Class:' in line:
                try:
                    class_hex = line.split('Class:')[1].strip()
                    class_val = int(class_hex, 16)
                    # Major device class is bits 8-12, 0x04 = Audio/Video
                    major_class = (class_val >> 8) & 0x1F
                    if major_class == 0x04:
                        return True
                except (ValueError, IndexError):
                    pass
        return False

    def get_paired_devices(self):
        """Get only paired devices (not just known/seen devices)."""
        try:
            # Use 'devices Paired' to get only actually paired devices
            output = self._run_cmd(['bluetoothctl', 'devices', 'Paired'])
            devices = []
            for line in output.split('\n'):
                if not line:
                    continue
                parts = line.split(' ', 2)
                if len(parts) >= 3:
                    mac = parts[1]
                    name = parts[2]
                    # Validate MAC address and device name
                    if not self._is_valid_mac(mac):
                        continue
                    if not self._is_valid_device_name(name):
                        # If name looks invalid, try to use a cleaned version
                        name = name.strip()
                        if not name:
                            continue
                    devices.append({'mac': mac, 'name': name, 'paired': True})
            return devices
        except (subprocess.SubprocessError, OSError):
            return []

    def start_scan(self, callback):
        # Use lock to prevent race condition on is_scanning check
        with self._lock:
            if self.is_scanning:
                return
            self.is_scanning = True
            self.found_devices = {}
        
        def scan_worker():
            # Start bluetoothctl scan in background
            self.scan_process = subprocess.Popen(
                ['bluetoothctl'], 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                encoding='utf-8',
                bufsize=1
            )
            
            try:
                self.scan_process.stdin.write("scan on\n")
                self.scan_process.stdin.flush()
                
                while self.is_scanning and self.scan_process.poll() is None:
                    line = self.scan_process.stdout.readline()
                    if not line: break
                    
                    clean = self._clean_ansi(line).strip()
                    
                    # Parse Device Found
                    # Format: [NEW] Device XX:XX:XX:XX:XX:XX Name
                    if "Device" in clean and (("NEW" in clean) or ("CHG" in clean)):
                        parts = clean.split(' ')
                        try:
                            mac_idx = parts.index("Device") + 1
                            mac = parts[mac_idx]

                            # Validate MAC address format
                            if not self._is_valid_mac(mac):
                                continue

                            # Grab name (everything after MAC)
                            name = " ".join(parts[mac_idx+1:])

                            # Filter junk names
                            if not self._is_valid_device_name(name):
                                continue

                            # Filter for audio devices only
                            if not self._is_audio_device(mac):
                                continue

                            # Update Dict
                            self.found_devices[mac] = {'mac': mac, 'name': name, 'paired': False}

                            # Fire Callback
                            callback(list(self.found_devices.values()))
                        except (ValueError, IndexError):
                            pass
            except (OSError, IOError):
                pass
            finally:
                self._stop_scan_process()

        t = threading.Thread(target=scan_worker)
        t.daemon = True
        t.start()

    def stop_scan(self):
        self.is_scanning = False
        self._stop_scan_process()

    def _stop_scan_process(self):
        if self.scan_process:
            try:
                self.scan_process.stdin.write("scan off\n")
                self.scan_process.stdin.write("exit\n")
                self.scan_process.stdin.flush()
                time.sleep(0.1)
                self.scan_process.terminate()
                self.scan_process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                pass
            self.scan_process = None

    def connect_async(self, mac, callback):
        if not self._is_valid_mac(mac):
            callback(False, "INVALID MAC")
            return
        t = threading.Thread(target=self._connect_worker, args=(mac, callback))
        t.daemon = True
        t.start()

    def _connect_worker(self, mac, callback):
        # Sanitize MAC for logging (already validated format)
        safe_mac = shlex.quote(mac)
        logger.info(f"Bluetooth connecting to {safe_mac}")

        # 1. Pre-check: If already connected, don't even start bluetoothctl
        if self.is_connected(mac):
            logger.info(f"Bluetooth device {safe_mac} already connected")
            callback(True, "ALREADY CONNECTED")
            return

        proc = subprocess.Popen(
            ['bluetoothctl'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='utf-8',
            bufsize=1
        )

        def send(cmd):
            try:
                proc.stdin.write(cmd + "\n")
                proc.stdin.flush()
            except (OSError, IOError):
                pass

        # Trust and Pair first (good practice)
        send(f'trust {mac}')
        send(f'pair {mac}')
        time.sleep(1)
        send(f'connect {mac}')

        success = False
        msg = "FAILED"
        start_time = time.time()
        retry_count = 0
        max_retries = 3

        while time.time() - start_time < 25:
            line = proc.stdout.readline()
            if not line:
                break
            clean_line = self._clean_ansi(line).strip()

            if "yes/no" in clean_line.lower() or "confirm" in clean_line.lower():
                send("yes")

            # --- SUCCESS CASES ---
            if "Connection successful" in clean_line:
                success = True
                msg = "CONNECTED"
                logger.info(f"Bluetooth connected to {safe_mac}")
                break

            # --- FAILURE / BUSY CASES ---
            if "br-connection-busy" in clean_line or "Device is already connected" in clean_line:
                time.sleep(1)
                if self.is_connected(mac):
                    success = True
                    msg = "CONNECTED"
                    break
                elif retry_count < max_retries:
                    retry_count += 1
                    logger.debug(f"Bluetooth busy, retry {retry_count}/{max_retries}")
                    time.sleep(2)
                    send(f'connect {mac}')
                else:
                    logger.warning(f"Bluetooth connection busy after {max_retries} retries")
                    break

            if "Failed to connect" in clean_line and "busy" not in clean_line:
                if retry_count < max_retries:
                    retry_count += 1
                    logger.debug(f"Bluetooth connect failed, retry {retry_count}/{max_retries}")
                    time.sleep(2)
                    send(f'connect {mac}')
                else:
                    logger.warning(f"Bluetooth connection failed after {max_retries} retries")
                    break

        try:
            proc.terminate()
            proc.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass

        # Final safety check
        if not success and self.is_connected(mac):
            success = True
            msg = "CONNECTED"
            logger.info(f"Bluetooth connected to {safe_mac} (verified)")

        if not success:
            logger.warning(f"Bluetooth connection to {safe_mac} failed: {msg}")
        else:
            # Set audio output to the connected device after a brief delay
            # to allow PulseAudio to register the new sink
            time.sleep(1.5)
            if self._is_audio_device(mac):
                self.set_audio_output(mac)

        callback(success, msg)

    def forget_device(self, mac):
        if not self._is_valid_mac(mac):
            return
        self._run_cmd(['bluetoothctl', 'remove', mac])

    def disconnect_device(self, mac):
        if not self._is_valid_mac(mac):
            return
        self._run_cmd(['bluetoothctl', 'disconnect', mac])

    def set_audio_output(self, mac):
        """Set audio output to the connected Bluetooth device.

        Args:
            mac: MAC address of the Bluetooth device
        """
        if not self._is_valid_mac(mac):
            return False

        try:
            # Get PulseAudio sinks
            result = subprocess.check_output(
                ["pactl", "list", "sinks", "short"],
                text=True, stderr=subprocess.DEVNULL, timeout=2
            )

            # Find sink matching the Bluetooth device (bluez_sink format)
            # MAC address in sink name uses underscores instead of colons
            mac_underscore = mac.replace(':', '_')
            for line in result.split('\n'):
                if mac_underscore.lower() in line.lower() or 'bluez' in line.lower():
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        sink_name = parts[1]
                        # Set as default sink
                        subprocess.run(
                            ["pactl", "set-default-sink", sink_name],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
                        )
                        # Move existing streams to new sink
                        self._move_streams_to_sink(sink_name)
                        logger.info(f"Audio output set to Bluetooth device: {sink_name}")
                        return True

            logger.warning(f"No audio sink found for Bluetooth device {mac}")
            return False
        except (subprocess.SubprocessError, OSError) as e:
            logger.error(f"Failed to set Bluetooth audio output: {e}")
            return False

    def _move_streams_to_sink(self, sink_name):
        """Move all playing streams to the specified sink."""
        try:
            # Get list of sink inputs
            result = subprocess.check_output(
                ["pactl", "list", "short", "sink-inputs"],
                text=True, stderr=subprocess.DEVNULL, timeout=2
            )
            for line in result.strip().split('\n'):
                if line:
                    parts = line.split('\t')
                    if parts:
                        input_id = parts[0]
                        subprocess.run(
                            ["pactl", "move-sink-input", input_id, sink_name],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
                        )
        except (subprocess.SubprocessError, OSError):
            pass
