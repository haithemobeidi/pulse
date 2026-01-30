"""
Hardware Collector

Collects GPU, CPU, and RAM information using PowerShell queries.
Critical for tracking GPU driver versions and monitoring changes.
"""

import json
from typing import Optional
from backend.collectors.base import BaseCollector
from backend.database import GPUState, HardwareState
from backend.utils.powershell import (
    get_gpu_info,
    get_cpu_info,
    get_memory_info,
    get_gpu_temperature,
    get_display_driver_version
)


class HardwareCollector(BaseCollector):
    """Collects GPU, CPU, memory, and hardware information"""

    def collect(self, snapshot_id: int) -> bool:
        """
        Collect hardware information for snapshot.

        Args:
            snapshot_id: Snapshot ID to associate data with

        Returns:
            True if any data was collected successfully
        """
        collected = False

        # Collect GPU data
        if self._collect_gpu(snapshot_id):
            collected = True
            self.log_info("GPU data collected")

        # Collect CPU data
        if self._collect_cpu(snapshot_id):
            collected = True
            self.log_info("CPU data collected")

        # Collect memory data
        if self._collect_memory(snapshot_id):
            collected = True
            self.log_info("Memory data collected")

        return collected

    def _collect_gpu(self, snapshot_id: int) -> bool:
        """
        Collect GPU information.

        Critical for user's monitor blackout debugging:
        - Tracks GPU driver version changes
        - Monitors temperature (correlates with stability)
        - Records VRAM usage
        """
        try:
            gpu_list = get_gpu_info()

            if not gpu_list:
                self.log_warning("No GPU devices found")
                return False

            # Process first GPU (usually the primary discrete GPU)
            gpu = gpu_list[0] if isinstance(gpu_list, list) else gpu_list

            gpu_name = gpu.get("Name", "Unknown GPU")
            driver_version = gpu.get("DriverVersion")

            # Try to get more detailed driver info if available
            if not driver_version:
                driver_version = self._get_driver_version_fallback()

            # Get temperature if available
            temp = self._safe_execute(get_gpu_temperature)

            # Get VRAM info (AdapterRAM in bytes)
            vram_total = gpu.get("AdapterRAM")
            if vram_total:
                # Convert bytes to MB
                vram_total_mb = int(vram_total) // (1024 * 1024)
            else:
                vram_total_mb = None

            # Create GPU state record
            gpu_state = GPUState(
                snapshot_id=snapshot_id,
                gpu_name=gpu_name,
                driver_version=driver_version,
                vram_total_mb=vram_total_mb,
                vram_used_mb=None,  # Requires additional query
                temperature_c=temp,
                power_draw_w=None,  # Requires specialized tools
                clock_speed_mhz=None
            )

            self.db.create_gpu_state(gpu_state)
            self.log_info(f"Recorded GPU: {gpu_name} (Driver: {driver_version})")
            return True

        except Exception as e:
            self.log_error(f"Failed to collect GPU data: {e}")
            return False

    def _get_driver_version_fallback(self) -> Optional[str]:
        """
        Fallback method to get driver version from registry.

        Used if WMI doesn't provide driver version.
        """
        try:
            version = get_display_driver_version()
            if version:
                self.log_info(f"Got driver version from registry: {version}")
            return version
        except Exception as e:
            self.log_warning(f"Could not get driver version: {e}")
            return None

    def _collect_cpu(self, snapshot_id: int) -> bool:
        """Collect CPU information"""
        try:
            cpu_info = get_cpu_info()

            if not cpu_info:
                self.log_warning("No CPU info available")
                return False

            # Store as JSON in hardware_state table
            component_data = json.dumps({
                "name": cpu_info.get("Name"),
                "cores": cpu_info.get("NumberOfCores"),
                "logical_processors": cpu_info.get("NumberOfLogicalProcessors"),
                "max_clock_speed_mhz": cpu_info.get("MaxClockSpeed")
            })

            hardware = HardwareState(
                snapshot_id=snapshot_id,
                component_type="cpu",
                component_data=component_data
            )

            self.db.create_hardware_state(hardware)
            self.log_info(f"Recorded CPU: {cpu_info.get('Name')}")
            return True

        except Exception as e:
            self.log_error(f"Failed to collect CPU data: {e}")
            return False

    def _collect_memory(self, snapshot_id: int) -> bool:
        """Collect memory information"""
        try:
            mem_info = get_memory_info()

            if not mem_info:
                self.log_warning("No memory info available")
                return False

            # Convert KB to GB
            total_kb = mem_info.get("TotalVisibleMemorySize", 0)
            free_kb = mem_info.get("FreePhysicalMemory", 0)

            component_data = json.dumps({
                "total_gb": round(total_kb / 1024 / 1024, 2),
                "free_gb": round(free_kb / 1024 / 1024, 2),
                "used_gb": round((total_kb - free_kb) / 1024 / 1024, 2),
                "percent_free": round(100 * free_kb / total_kb, 1) if total_kb > 0 else 0
            })

            hardware = HardwareState(
                snapshot_id=snapshot_id,
                component_type="memory",
                component_data=component_data
            )

            self.db.create_hardware_state(hardware)
            self.log_info(f"Recorded Memory: {component_data}")
            return True

        except Exception as e:
            self.log_error(f"Failed to collect memory data: {e}")
            return False
