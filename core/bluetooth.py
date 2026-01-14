import subprocess
import time
import threading
import re
import signal
import os

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
            "light"
        ]

    def _run_cmd(self, cmd):
        try:
            return subprocess.check_output(cmd, encoding='utf-8', stderr=subprocess.DEVNULL)
        except Exception:
            return ""

    def _clean_ansi(self, text):
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def is_connected(self, mac):
        """Checks if a specific device is currently connected."""
        info = self._run_cmd(['bluetoothctl', 'info', mac])
        return "Connected: yes" in info

    def get_paired_devices(self):
        try:
            output = self._run_cmd(['bluetoothctl', 'devices'])
            devices = []
            for line in output.split('\n'):
                if not line: continue
                parts = line.split(' ', 2)
                if len(parts) >= 3:
                    devices.append({'mac': parts[1], 'name': parts[2], 'paired': True})
            return devices
        except: return []

    def start_scan(self, callback):
        if self.is_scanning: return
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
                            # Grab name (everything after MAC)
                            name = " ".join(parts[mac_idx+1:])
                            
                            # Filter junk
                            if not name or any(x in name for x in self.ignore_keywords): continue
                            if len(name) < 2: continue
                            
                            # Update Dict
                            self.found_devices[mac] = {'mac': mac, 'name': name, 'paired': False}
                            
                            # Fire Callback
                            callback(list(self.found_devices.values()))
                        except: pass
            except: pass
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
            except: pass
            self.scan_process = None

    def connect_async(self, mac, callback):
        t = threading.Thread(target=self._connect_worker, args=(mac, callback))
        t.daemon = True
        t.start()

    def _connect_worker(self, mac, callback):
        # 1. Pre-check: If already connected, don't even start bluetoothctl
        if self.is_connected(mac):
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
            except: pass

        # Trust and Pair first (good practice)
        send(f'trust {mac}')
        send(f'pair {mac}')
        time.sleep(1)
        send(f'connect {mac}')

        success = False
        msg = "FAILED"
        start_time = time.time()
        
        while time.time() - start_time < 25: 
            line = proc.stdout.readline()
            if not line: break
            clean_line = self._clean_ansi(line).strip()
            
            # Debug log (Optional, comment out to reduce noise)
            # if clean_line: print(f"[BT LOG]: {clean_line}")

            if "yes/no" in clean_line.lower() or "confirm" in clean_line.lower():
                send("yes")
            
            # --- SUCCESS CASES ---
            if "Connection successful" in clean_line:
                success = True
                msg = "CONNECTED"
                break
            
            # --- FAILURE / BUSY CASES ---
            # KEY FIX: If busy, check if we are actually connected
            if "br-connection-busy" in clean_line or "Device is already connected" in clean_line:
                time.sleep(1)
                if self.is_connected(mac):
                    success = True
                    msg = "CONNECTED"
                    break
                else:
                    # Actually busy with something else? Wait before retry
                    time.sleep(2)
                    send(f'connect {mac}')

            if "Failed to connect" in clean_line and "busy" not in clean_line:
                # Genuine failure, wait and retry
                time.sleep(2)
                send(f'connect {mac}')

        try: proc.terminate()
        except: pass
        
        # Final safety check
        if not success and self.is_connected(mac):
            success = True
            msg = "CONNECTED"

        callback(success, msg)

    def forget_device(self, mac):
        self._run_cmd(['bluetoothctl', 'remove', mac])

    def disconnect_device(self, mac):
        self._run_cmd(['bluetoothctl', 'disconnect', mac])
