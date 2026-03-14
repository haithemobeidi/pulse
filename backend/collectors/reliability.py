"""
Reliability Monitor Collector

Collects Windows Reliability Monitor data via WMI (Win32_ReliabilityRecords).
This is a goldmine for troubleshooting - it tracks:
- Application crashes and hangs
- Driver crashes/failures
- Software installs/uninstalls
- OS updates and failures
- Hardware failures
- Misc failures

Also retrieves the system stability index (1-10 scale).
"""

import subprocess
import json
import logging
from typing import List, Dict, Any, Optional
from backend.collectors.base import BaseCollector
from backend.database import ReliabilityRecord

logger = logging.getLogger(__name__)


class ReliabilityCollector(BaseCollector):
    """Collects Windows Reliability Monitor data"""

    # Map Win32_ReliabilityRecords EventIdentifier ranges to readable types
    # and RecordType values to our categories
    RECORD_TYPE_MAP = {
        # Software installs/uninstalls
        "MsiInstaller": "app_install",
        "WindowsUpdateClient": "os_update",
        "Application Error": "app_crash",
        "Application Hang": "app_crash",
        "Windows Error Reporting": "app_crash",
        "BlueScreen": "os_crash",
        "BugCheck": "os_crash",
        "Display": "driver_crash",
        "nvlddmkm": "driver_crash",
        "atikmdag": "driver_crash",
        "igfx": "driver_crash",
        "Kernel-Power": "os_crash",
        "EventLog": "misc_failure",
        "WHEA-Logger": "hardware_failure",
    }

    def collect(self, snapshot_id: int, days: int = 30) -> bool:
        """
        Collect reliability monitor data for snapshot.

        Args:
            snapshot_id: Snapshot ID to associate data with
            days: How many days back to look (default 30)

        Returns:
            True if any records were collected
        """
        try:
            records = self._get_reliability_records(days)

            if not records:
                self.log_warning("No reliability records found")
                return False

            # Also get stability index
            stability_index = self._get_stability_index()

            recorded_count = 0
            for record in records:
                try:
                    record_type = self._classify_record(record)

                    reliability_record = ReliabilityRecord(
                        snapshot_id=snapshot_id,
                        record_type=record_type,
                        source_name=record.get("SourceName", "Unknown"),
                        event_message=record.get("Message", "")[:2000],  # Truncate long messages
                        event_time=record.get("TimeGenerated", ""),
                        product_name=record.get("ProductName", ""),
                        stability_index=stability_index
                    )

                    self.db.create_reliability_record(reliability_record)
                    recorded_count += 1

                except Exception as e:
                    self.log_warning(f"Failed to record reliability entry: {e}")

            self.log_info(f"Recorded {recorded_count} reliability records (stability index: {stability_index})")
            return recorded_count > 0

        except Exception as e:
            self.log_error(f"Failed to collect reliability data: {e}")
            return False

    def _get_reliability_records(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Query Win32_ReliabilityRecords via PowerShell.

        This reads the same data that Reliability Monitor shows in Windows.
        Filters to significant events (crashes, installs, failures).

        Args:
            days: How many days back to look

        Returns:
            List of reliability record dictionaries
        """
        # PowerShell query for reliability records
        # Win32_ReliabilityRecords contains all reliability monitor data
        ps_command = (
            f"$cutoff = (Get-Date).AddDays(-{days}).ToString('yyyyMMddHHmmss.000000+000'); "
            "$records = Get-CimInstance -ClassName Win32_ReliabilityRecords "
            "-ErrorAction SilentlyContinue | "
            f"Where-Object {{ $_.TimeGenerated -ge $cutoff }} | "
            "Select-Object @{Name='SourceName';Expression={$_.SourceName}}, "
            "@{Name='Message';Expression={if($_.Message.Length -gt 500){$_.Message.Substring(0,500)}else{$_.Message}}}, "
            "@{Name='TimeGenerated';Expression={$_.TimeGenerated.ToString('yyyy-MM-dd HH:mm:ss')}}, "
            "@{Name='ProductName';Expression={$_.ProductName}}, "
            "@{Name='EventIdentifier';Expression={$_.EventIdentifier}}, "
            "@{Name='RecordNumber';Expression={$_.RecordNumber}} "
            "-First 200; "
            "$records | ConvertTo-Json -Depth 3"
        )

        try:
            result = subprocess.run(
                ["powershell.exe", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0 and result.stdout.strip():
                try:
                    records = json.loads(result.stdout)
                    if not isinstance(records, list):
                        records = [records]

                    self.log_info(f"Retrieved {len(records)} reliability records from last {days} days")
                    return records
                except json.JSONDecodeError as e:
                    self.log_warning(f"Failed to parse reliability records JSON: {e}")
            else:
                if result.stderr:
                    self.log_warning(f"PowerShell stderr: {result.stderr[:200]}")

        except subprocess.TimeoutExpired:
            self.log_warning("Reliability Monitor query timed out")
        except Exception as e:
            self.log_error(f"Failed to query reliability records: {e}")

        return []

    def _get_stability_index(self) -> Optional[float]:
        """
        Get the current Windows stability index (1-10 scale).

        Uses Win32_ReliabilityStabilityMetrics for the most recent value.

        Returns:
            Stability index (1.0 to 10.0) or None
        """
        ps_command = (
            "$metric = Get-CimInstance -ClassName Win32_ReliabilityStabilityMetrics "
            "-ErrorAction SilentlyContinue | "
            "Sort-Object -Property TimeGenerated -Descending | "
            "Select-Object -First 1; "
            "if ($metric) { $metric.SystemStabilityIndex } else { 'null' }"
        )

        try:
            result = subprocess.run(
                ["powershell.exe", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode == 0 and result.stdout.strip():
                value = result.stdout.strip()
                if value and value != 'null':
                    try:
                        index = float(value)
                        self.log_info(f"System stability index: {index:.2f}/10")
                        return round(index, 2)
                    except ValueError:
                        pass

        except Exception as e:
            self.log_warning(f"Could not get stability index: {e}")

        return None

    def _classify_record(self, record: Dict[str, Any]) -> str:
        """
        Classify a reliability record into a category.

        Args:
            record: Raw reliability record from WMI

        Returns:
            Record type string (app_crash, driver_crash, os_crash, app_install, etc.)
        """
        source = record.get("SourceName", "")
        message = record.get("Message", "").lower()
        product = record.get("ProductName", "").lower()

        # Check source name against known patterns
        for pattern, record_type in self.RECORD_TYPE_MAP.items():
            if pattern.lower() in source.lower():
                return record_type

        # Check message content for clues
        if any(word in message for word in ["install", "installed", "setup"]):
            if "uninstall" in message or "removed" in message:
                return "app_uninstall"
            return "app_install"

        if any(word in message for word in ["crash", "fault", "error", "stopped working"]):
            if any(word in message for word in ["driver", "display", "gpu", "nvidia", "amd"]):
                return "driver_crash"
            return "app_crash"

        if any(word in message for word in ["update", "patch", "kb"]):
            return "os_update"

        if any(word in message for word in ["blue screen", "bugcheck", "kernel"]):
            return "os_crash"

        if any(word in message for word in ["hardware", "disk", "memory", "whea"]):
            return "hardware_failure"

        return "misc_failure"
