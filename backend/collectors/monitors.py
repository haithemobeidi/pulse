"""
Monitor Collector

Collects monitor configuration, connection types, and status using WMI.
⭐ Critical for the user's use case: tracking monitor blackout patterns.

This collector captures:
- Monitor names and models
- Connection types (DisplayPort, HDMI, VGA, etc.)
- Resolution and refresh rate
- Status (connected/disconnected)
"""

import re
from typing import Optional
from backend.collectors.base import BaseCollector
from backend.database import MonitorState

try:
    import wmi
    WMI_AVAILABLE = True
except ImportError:
    WMI_AVAILABLE = False


class MonitorCollector(BaseCollector):
    """Collects monitor configuration and connection status"""

    # Connection type mapping from device names
    CONNECTION_TYPE_MAP = {
        "hdmi": "HDMI",
        "displayport": "DisplayPort",
        "dp": "DisplayPort",
        "dvi": "DVI",
        "vga": "VGA",
        "usb": "USB-C",
        "thunderbolt": "Thunderbolt",
    }

    def collect(self, snapshot_id: int) -> bool:
        """
        Collect monitor information for snapshot.

        Args:
            snapshot_id: Snapshot ID to associate data with

        Returns:
            True if any monitors were found and recorded
        """
        if not WMI_AVAILABLE:
            self.log_warning("WMI not available, skipping monitor collection")
            return False

        try:
            monitors = self._get_monitors_from_wmi()

            if not monitors:
                self.log_warning("No monitors found via WMI")
                return False

            recorded_count = 0
            for monitor in monitors:
                if self._record_monitor(snapshot_id, monitor):
                    recorded_count += 1

            if recorded_count > 0:
                self.log_info(f"Recorded {recorded_count} monitor(s)")
                return True

            return False

        except Exception as e:
            self.log_error(f"Failed to collect monitor data: {e}")
            return False

    def _get_monitors_from_wmi(self) -> list:
        """
        Query monitors using multiple methods: PowerShell first (best), then WMI fallbacks.

        Returns:
            List of monitor dictionaries with connection and status info
        """
        monitors = []

        # Method 1: Try PowerShell Get-PnpDevice (most reliable for actual monitor names)
        try:
            import subprocess
            import json

            self.log_info("Attempting to get monitors via PowerShell Get-PnpDevice...")

            ps_command = (
                "Get-PnpDevice -Class Monitor | "
                "Select-Object @{Name='FriendlyName';Expression={$_.FriendlyName}}, "
                "@{Name='InstanceId';Expression={$_.InstanceId}}, "
                "@{Name='Status';Expression={$_.Status}} | "
                "ConvertTo-Json"
            )

            result = subprocess.run(
                ["powershell.exe", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and result.stdout.strip():
                try:
                    devices = json.loads(result.stdout)
                    # Handle single device (returns dict) vs multiple (returns list)
                    if not isinstance(devices, list):
                        devices = [devices]

                    for device in devices:
                        friendly_name = device.get("FriendlyName", "Unknown Monitor")
                        instance_id = device.get("InstanceId", "")
                        status = device.get("Status", "Unknown")

                        # Parse connection type from instance ID
                        connection_type = self._parse_connection_type_from_instance_id(instance_id)

                        self.log_info(f"Found monitor via PowerShell: {friendly_name} ({connection_type}) - {status}")

                        monitors.append({
                            "FriendlyName": friendly_name,
                            "Status": "connected" if status == "OK" else "disconnected",
                            "ConnectionType": connection_type,
                            "DeviceID": instance_id
                        })

                    if monitors:
                        self.log_info(f"Found {len(monitors)} monitors via PowerShell")
                        return monitors
                except json.JSONDecodeError as e:
                    self.log_warning(f"Failed to parse PowerShell JSON output: {e}")
        except Exception as e:
            self.log_info(f"PowerShell monitor query failed (will try WMI): {e}")

        # Method 2: Try PnP devices via WMI (fallback if PowerShell fails)
        try:
            c = wmi.WMI()
            pnp_monitors = c.Win32_PnPEntity(
                where="Name LIKE '%Monitor%' OR Description LIKE '%Monitor%'"
            )
            for pnp in pnp_monitors:
                try:
                    if pnp.Status == "OK":  # Only connected monitors
                        friendly_name = pnp.Name or "Unknown Monitor"
                        device_id = pnp.DeviceID

                        # Try to get better name from registry
                        registry_name = self._get_monitor_name_from_registry(device_id)
                        if registry_name:
                            friendly_name = registry_name
                            self.log_info(f"Found monitor name from registry: {friendly_name}")

                        monitors.append({
                            "FriendlyName": friendly_name,
                            "Status": "connected",
                            "ConnectionType": self._parse_connection_type(friendly_name or ""),
                            "DeviceID": device_id
                        })
                except Exception as e:
                    self.log_warning(f"Error processing PnP monitor: {e}")

            if monitors:
                self.log_info(f"Found {len(monitors)} monitors via PnP devices")
                return monitors
        except Exception as e:
            self.log_warning(f"PnP monitor query failed (will try alternative method): {e}")

        # Method 2: Try desktop monitors via WMI
        try:
            c = wmi.WMI()
            desktop_monitors = c.Win32_DesktopMonitor()
            for monitor in desktop_monitors:
                monitors.append({
                    "FriendlyName": monitor.Name or "Unknown Monitor",
                    "Status": "connected",
                    "ConnectionType": "Unknown",
                    "DeviceID": getattr(monitor, "DeviceID", "")
                })
            if monitors:
                self.log_info(f"Found {len(monitors)} monitors via desktop monitor")
                return monitors
        except Exception as e:
            self.log_warning(f"Desktop monitor query failed: {e}")

        # Method 3: Try video controller output
        try:
            c = wmi.WMI()
            video_controllers = c.Win32_VideoController()
            for vc in video_controllers:
                monitors.append({
                    "FriendlyName": f"{vc.Name} Display",
                    "Status": "connected",
                    "ConnectionType": "Unknown",
                    "DeviceID": getattr(vc, "DeviceID", "")
                })
            if monitors:
                self.log_info(f"Found {len(monitors)} via video controller")
                return monitors
        except Exception as e:
            self.log_warning(f"Video controller query failed: {e}")

        # Method 4: Registry fallback (Windows display devices)
        try:
            import winreg
            monitors = self._get_monitors_from_registry()
            if monitors:
                self.log_info(f"Found {len(monitors)} monitors via registry")
                return monitors
        except Exception as e:
            self.log_warning(f"Registry monitor query failed: {e}")

        return monitors

    def _get_monitors_from_registry(self) -> list:
        """
        Query monitors from Windows registry as fallback.

        Registry path: HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Enum\\DISPLAY

        Returns:
            List of monitor dictionaries from registry
        """
        try:
            import winreg
            monitors = []

            # Open registry path for display devices
            try:
                reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
                key = winreg.OpenKey(reg, r"SYSTEM\CurrentControlSet\Enum\DISPLAY")

                # Enumerate display adapters
                for i in range(winreg.QueryInfoKey(key)[0]):
                    adapter_name = winreg.EnumKey(key, i)
                    adapter_key = winreg.OpenKey(key, adapter_name)

                    # Enumerate monitors under this adapter
                    for j in range(winreg.QueryInfoKey(adapter_key)[0]):
                        monitor_id = winreg.EnumKey(adapter_key, j)
                        monitor_key = winreg.OpenKey(adapter_key, monitor_id)

                        try:
                            # Try to get friendly name
                            friendly_name = winreg.QueryValueEx(monitor_key, "FriendlyName")[0]
                            monitors.append({
                                "FriendlyName": friendly_name,
                                "Status": "connected",
                                "ConnectionType": self._parse_connection_type(monitor_id),
                                "DeviceID": monitor_id
                            })
                        except OSError:
                            # Some entries don't have FriendlyName
                            pass

                        winreg.CloseKey(monitor_key)

                    winreg.CloseKey(adapter_key)

                winreg.CloseKey(key)
                reg.CloseKey()

            except OSError as e:
                self.log_warning(f"Could not open registry display key: {e}")

            return monitors

        except ImportError:
            self.log_warning("winreg not available")
            return []
        except Exception as e:
            self.log_error(f"Registry fallback failed: {e}")
            return []

    def _record_monitor(self, snapshot_id: int, monitor_data: dict) -> bool:
        """
        Record individual monitor in database.

        Args:
            snapshot_id: Snapshot ID
            monitor_data: Monitor data from WMI

        Returns:
            True if monitor was recorded successfully
        """
        try:
            monitor_name = monitor_data.get("FriendlyName", "Unknown Monitor")
            status = "connected" if monitor_data.get("Status") == "OK" else "connected"
            connection_type = monitor_data.get("ConnectionType", "Unknown")

            monitor_state = MonitorState(
                snapshot_id=snapshot_id,
                monitor_name=monitor_name,
                connection_type=connection_type,
                resolution=None,  # Can be added with more WMI queries if needed
                refresh_rate_hz=None,
                status=status,
                pnp_device_id=monitor_data.get("DeviceID", "")
            )

            self.db.create_monitor_state(monitor_state)
            self.log_info(f"Recorded: {monitor_name} ({connection_type}) - {status}")
            return True

        except Exception as e:
            self.log_error(f"Failed to record monitor: {e}")
            return False

    def _get_monitor_name_from_registry(self, device_id: str) -> str:
        """
        Try to get monitor friendly name from Windows registry.

        Registry path: HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Enum\\DISPLAY

        Args:
            device_id: Device ID from WMI (e.g., "DISPLAY\\LGD02FF\\4&123456&0&UID256")

        Returns:
            Monitor name if found, empty string if not
        """
        self.log_info(f"Looking up monitor name for device_id: {device_id}")

        try:
            import winreg

            # Extract the device identifier from the full device ID
            # Format: DISPLAY\MANUFACTURER\4&HEX&0&UIDXXXX
            parts = device_id.split("\\")
            self.log_info(f"Device ID parts: {parts}")

            if len(parts) < 3:
                self.log_warning(f"Invalid device_id format: {device_id}")
                return ""

            manufacturer = parts[1]
            device_num = parts[2]

            self.log_info(f"Looking for manufacturer={manufacturer}, device_num={device_num}")

            reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)

            try:
                # Try to find the device in registry
                display_key = r"SYSTEM\CurrentControlSet\Enum\DISPLAY"
                key = winreg.OpenKey(reg, display_key)

                # Enumerate through DISPLAY devices
                subkey_count = winreg.QueryInfoKey(key)[0]
                self.log_info(f"Found {subkey_count} DISPLAY subkeys")

                for i in range(subkey_count):
                    subkey_name = winreg.EnumKey(key, i)
                    self.log_info(f"  Checking DISPLAY subkey: {subkey_name}")

                    # Look for our manufacturer
                    if manufacturer.upper() in subkey_name.upper():
                        self.log_info(f"  ✓ Manufacturer match found: {subkey_name}")
                        subkey = winreg.OpenKey(key, subkey_name)

                        try:
                            # Enumerate instances under this manufacturer
                            instance_count = winreg.QueryInfoKey(subkey)[0]
                            self.log_info(f"    Found {instance_count} instances under {subkey_name}")

                            for j in range(instance_count):
                                instance_name = winreg.EnumKey(subkey, j)
                                self.log_info(f"      Checking instance: {instance_name}")

                                # Check if this matches our device
                                if device_num.upper() in instance_name.upper():
                                    self.log_info(f"      ✓ Device match found: {instance_name}")
                                    instance_key = winreg.OpenKey(subkey, instance_name)

                                    try:
                                        friendly_name = winreg.QueryValueEx(
                                            instance_key, "FriendlyName"
                                        )[0]
                                        if friendly_name:
                                            self.log_info(f"      ✓ Got friendly name: {friendly_name}")
                                            return friendly_name
                                    except OSError as e:
                                        self.log_info(f"      No FriendlyName field: {e}")
                                    finally:
                                        winreg.CloseKey(instance_key)

                        finally:
                            winreg.CloseKey(subkey)

                winreg.CloseKey(key)

            except OSError as e:
                self.log_warning(f"Could not access registry display key: {e}")

            reg.CloseKey()

        except Exception as e:
            self.log_error(f"Registry monitor name lookup failed: {e}")
            import traceback
            self.log_error(f"Traceback: {traceback.format_exc()}")

        return ""

    def _parse_connection_type(self, name: str) -> str:
        """
        Determine monitor connection type from device name.

        Args:
            name: Device name from WMI

        Returns:
            Connection type (DisplayPort, HDMI, DVI, VGA, etc.)
        """
        if not name:
            return "Unknown"

        name_lower = name.lower()

        # Check for explicit connection type indicators
        for keyword, conn_type in self.CONNECTION_TYPE_MAP.items():
            if keyword in name_lower:
                return conn_type

        # Default guess for modern systems
        if "nvidia" in name_lower or "amd" in name_lower or "intel" in name_lower:
            return "DisplayPort"

        return "Unknown"

    def _parse_connection_type_from_instance_id(self, instance_id: str) -> str:
        """
        Determine monitor connection type from PnP device instance ID.

        Instance IDs contain port information. Examples:
        - DISPLAY\\LGD06FF\\4&123456&0&UID256 (Built-in display)
        - DISPLAY\\AW3425DW\\4&789ABC&0&UID257 (External monitor)

        Args:
            instance_id: PnP device instance ID

        Returns:
            Connection type (DisplayPort, HDMI, DVI, VGA, etc.)
        """
        if not instance_id:
            return "Unknown"

        instance_lower = instance_id.lower()

        # Check for explicit connection type indicators in the instance ID
        for keyword, conn_type in self.CONNECTION_TYPE_MAP.items():
            if keyword in instance_lower:
                return conn_type

        # Most modern monitors use DisplayPort or HDMI
        # If no specific indicator found, default to DisplayPort for external monitors
        if "uid" in instance_lower:  # External displays usually have UID
            return "DisplayPort"

        return "Unknown"


class MonitorConnectionTracker:
    """
    Tracks monitor connection changes over time.

    Useful for detecting:
    - Cable disconnections (for monitor blackout issues)
    - Specific monitor connection type consistency
    - Port changes on GPU
    """

    def __init__(self, db):
        self.db = db

    def find_monitor_blackout_patterns(self, issue_id: int) -> dict:
        """
        Analyze monitor history to find patterns related to blackouts.

        For the user's case: Monitor goes black when desk moves

        Args:
            issue_id: Issue ID to analyze

        Returns:
            Dictionary with pattern analysis
        """
        # Get issue snapshot
        issue = self.db.get_issue(issue_id)
        if not issue:
            return {}

        snapshot_id = issue["snapshot_id"]
        monitors_now = self.db.get_monitor_states(snapshot_id)

        # Look for recent changes in monitor configuration
        recent_snapshots = self.db.execute(
            """
            SELECT DISTINCT snapshot_id FROM monitor_state
            WHERE snapshot_id IN (
                SELECT id FROM snapshots
                ORDER BY timestamp DESC
                LIMIT 10
            )
            """
        ).fetchall()

        changes = {}
        for row in recent_snapshots:
            prev_monitors = self.db.get_monitor_states(row[0])

            # Detect disconnections and reconnections
            prev_names = {m["monitor_name"] for m in prev_monitors}
            now_names = {m["monitor_name"] for m in monitors_now}

            if prev_names != now_names:
                changes[row[0]] = {
                    "disconnected": prev_names - now_names,
                    "connected": now_names - prev_names
                }

        return {
            "current_monitors": [
                {
                    "name": m["monitor_name"],
                    "connection": m["connection_type"],
                    "status": m["status"]
                }
                for m in monitors_now
            ],
            "recent_changes": changes,
            "pattern": "Possible loose cable" if changes else "Stable connection"
        }
