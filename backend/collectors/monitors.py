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
        Query monitors using WMI with multiple fallback methods.

        Returns:
            List of monitor dictionaries with connection and status info
        """
        monitors = []

        # Method 1: Try PnP devices (most reliable for detection)
        try:
            c = wmi.WMI()
            pnp_monitors = c.Win32_PnPEntity(
                where="Name LIKE '%Monitor%' OR Description LIKE '%Monitor%'"
            )
            for pnp in pnp_monitors:
                if pnp.Status == "OK":  # Only connected monitors
                    monitors.append({
                        "FriendlyName": pnp.Name or "Unknown Monitor",
                        "Status": "connected",
                        "ConnectionType": self._parse_connection_type(pnp.Name or ""),
                        "DeviceID": pnp.DeviceID
                    })
            if monitors:
                self.log_info(f"Found {len(monitors)} monitors via PnP devices")
                return monitors
        except Exception as e:
            self.log_warning(f"PnP monitor query failed: {e}")

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
