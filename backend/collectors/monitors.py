"""
Monitor Collector

Collects monitor configuration, connection types, and status.
⭐ Critical for the user's use case: tracking monitor blackout patterns.

This collector captures:
- Monitor names and models
- Connection types (DisplayPort, HDMI, VGA, etc.)
- Resolution and refresh rate
- Status (connected/disconnected)
- PnP device IDs for tracking specific monitors
"""

import re
from typing import Optional
from backend.collectors.base import BaseCollector
from backend.database import MonitorState
from backend.utils.powershell import get_monitor_info


class MonitorCollector(BaseCollector):
    """Collects monitor configuration and connection status"""

    # Connection type mapping from PnP device names
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
        try:
            monitors = get_monitor_info()

            if not monitors:
                self.log_warning("No monitors found")
                return False

            # Ensure monitors is a list
            if not isinstance(monitors, list):
                monitors = [monitors]

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

    def _record_monitor(self, snapshot_id: int, monitor_data: dict) -> bool:
        """
        Record individual monitor in database.

        Args:
            snapshot_id: Snapshot ID
            monitor_data: Monitor data from PowerShell

        Returns:
            True if monitor was recorded successfully
        """
        try:
            monitor_name = monitor_data.get("FriendlyName", "Unknown Monitor")
            status = monitor_data.get("Status", "Unknown").lower()
            pnp_id = monitor_data.get("InstanceId", "")

            # Determine connection type from PnP device ID
            connection_type = self._parse_connection_type(pnp_id)

            # Map status values
            if "ok" in status or "present" in status:
                status = "connected"
            else:
                status = "disconnected"

            # Create monitor state record
            monitor_state = MonitorState(
                snapshot_id=snapshot_id,
                monitor_name=monitor_name,
                connection_type=connection_type,
                resolution=None,  # Requires WMI query
                refresh_rate_hz=None,  # Requires WMI query
                status=status,
                pnp_device_id=pnp_id
            )

            self.db.create_monitor_state(monitor_state)
            self.log_info(f"Recorded: {monitor_name} ({connection_type}) - {status}")
            return True

        except Exception as e:
            self.log_error(f"Failed to record monitor: {e}")
            return False

    def _parse_connection_type(self, pnp_id: str) -> str:
        r"""
        Determine monitor connection type from PnP device ID.

        PnP IDs follow patterns like:
        - DisplayLink: DISPLAY\DLKD\... or HDMI
        - NVIDIA: DISPLAY\NVDA\... with port info
        - AMD: DISPLAY\ATI\... with connection info
        - Generic HDMI/DP identifiers

        Args:
            pnp_id: PnP device instance ID

        Returns:
            Connection type (DisplayPort, HDMI, DVI, VGA, etc.)
        """
        if not pnp_id:
            return "Unknown"

        pnp_id_lower = pnp_id.lower()

        # Check for explicit connection type indicators in the ID
        for keyword, conn_type in self.CONNECTION_TYPE_MAP.items():
            if keyword in pnp_id_lower:
                return conn_type

        # If not explicitly marked, check for common patterns
        # Most modern monitors are either DisplayPort or HDMI
        # Default to DisplayPort for newer systems
        if "nvidia" in pnp_id_lower or "amd" in pnp_id_lower:
            # Likely a high-end monitor if using discrete GPU
            # DisplayPort is more common for gaming/professional monitors
            return "DisplayPort"

        return "Unknown"

    def _get_resolution_and_refresh(self, monitor_name: str) -> tuple:
        """
        Get resolution and refresh rate for monitor.

        Note: This requires additional WMI queries through Win32_DesktopMonitor
        or reading display settings. Currently not implemented but available
        for future enhancement.

        Args:
            monitor_name: Monitor friendly name

        Returns:
            Tuple of (resolution_string, refresh_rate_hz) or (None, None)
        """
        # TODO: Implement if needed
        # Requires Get-WmiObject Win32_DesktopMonitor -Filter "Name like '%{monitor_name}%'"
        return None, None


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
