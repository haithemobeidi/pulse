"""
Hardware Collector

Collects GPU, CPU, and RAM information using psutil and WMI.
Much simpler and more reliable than PowerShell approach.
"""

import json
from typing import Optional
from backend.collectors.base import BaseCollector
from backend.database import GPUState, HardwareState

try:
    import psutil
except ImportError:
    psutil = None

try:
    import wmi
except ImportError:
    wmi = None


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
        Collect GPU information using WMI.

        Returns:
            True if GPU data was collected successfully
        """
        self.log_info(f"Starting GPU collection for snapshot {snapshot_id}")

        if not wmi:
            self.log_warning("WMI not available, skipping GPU collection")
            return False

        try:
            self.log_info("Connecting to WMI...")
            c = wmi.WMI()
            self.log_info("Querying Win32_VideoController...")
            video_controllers = c.Win32_VideoController()
            self.log_info(f"Found {len(list(video_controllers))} video controller(s)")

            if not video_controllers:
                self.log_warning("No video controllers found via WMI")
                return False

            # Prefer discrete GPU (NVIDIA/AMD) over integrated graphics (Intel/AMD APU)
            # Priority: NVIDIA > AMD discrete > Intel/AMD integrated
            preferred_gpu = None
            backup_gpu = None

            for vc in video_controllers:
                gpu_name = vc.Name or "Unknown GPU"
                driver_version = vc.DriverVersion
                adapter_ram = vc.AdapterRAM

                self.log_info(f"Processing GPU: {gpu_name} (Driver: {driver_version}, RAM: {adapter_ram})")

                # Check if this is a discrete GPU
                is_nvidia = "nvidia" in gpu_name.lower()
                is_amd_discrete = "amd" in gpu_name.lower() and "radeon" in gpu_name.lower() and "graphics" not in gpu_name.lower()
                is_integrated = "intel" in gpu_name.lower() or ("amd" in gpu_name.lower() and "graphics" in gpu_name.lower())

                self.log_info(f"  is_nvidia={is_nvidia}, is_amd_discrete={is_amd_discrete}, is_integrated={is_integrated}")

                gpu_info = {
                    'name': gpu_name,
                    'driver': driver_version,
                    'vram': adapter_ram,
                    'is_discrete': is_nvidia or is_amd_discrete
                }

                # Prioritize NVIDIA
                if is_nvidia and not preferred_gpu:
                    self.log_info(f"  Setting as preferred GPU (NVIDIA)")
                    preferred_gpu = gpu_info
                # Then AMD discrete
                elif is_amd_discrete and not preferred_gpu:
                    self.log_info(f"  Setting as preferred GPU (AMD discrete)")
                    preferred_gpu = gpu_info
                # Save integrated as backup
                elif is_integrated and not backup_gpu:
                    self.log_info(f"  Setting as backup GPU (integrated)")
                    backup_gpu = gpu_info
                # Take any GPU if nothing preferred yet
                elif not preferred_gpu and not backup_gpu:
                    self.log_info(f"  Setting as backup GPU (fallback)")
                    backup_gpu = gpu_info

            # Use preferred GPU, fallback to backup
            gpu_to_record = preferred_gpu or backup_gpu
            self.log_info(f"Selected GPU: {gpu_to_record}")

            if not gpu_to_record:
                self.log_warning("No suitable GPU found")
                return False

            # Convert VRAM from bytes to MB (handle negative/invalid values)
            vram_bytes = gpu_to_record['vram']
            self.log_info(f"VRAM bytes: {vram_bytes}")

            if vram_bytes and vram_bytes > 0:
                vram_mb = int(vram_bytes) // (1024 * 1024)
            else:
                vram_mb = None

            self.log_info(f"Creating GPU state: name={gpu_to_record['name']}, driver={gpu_to_record['driver']}, vram_mb={vram_mb}")

            gpu_state = GPUState(
                snapshot_id=snapshot_id,
                gpu_name=gpu_to_record['name'],
                driver_version=gpu_to_record['driver'],
                vram_total_mb=vram_mb,
                vram_used_mb=None,  # WMI doesn't provide current usage
                temperature_c=None,  # Requires specialized tools
                power_draw_w=None,
                clock_speed_mhz=None
            )

            self.log_info(f"Saving GPU state to database...")
            self.db.create_gpu_state(gpu_state)
            self.log_info(f"✅ Recorded GPU: {gpu_to_record['name']} (Driver: {gpu_to_record['driver']}, VRAM: {vram_mb}MB)")
            return True

        except Exception as e:
            self.log_error(f"❌ Failed to collect GPU data: {e}")
            import traceback
            self.log_error(f"Traceback: {traceback.format_exc()}")
            return False

    def _collect_cpu(self, snapshot_id: int) -> bool:
        """Collect CPU information using psutil"""
        if not psutil:
            self.log_warning("psutil not installed, skipping CPU collection")
            return False

        try:
            # Get CPU info
            cpu_count = psutil.cpu_count(logical=False)  # Physical cores
            cpu_count_logical = psutil.cpu_count(logical=True)  # Logical processors
            cpu_freq = psutil.cpu_freq()
            cpu_percent = psutil.cpu_percent(interval=1)

            component_data = json.dumps({
                "physical_cores": cpu_count,
                "logical_processors": cpu_count_logical,
                "frequency_mhz": int(cpu_freq.current) if cpu_freq else None,
                "max_frequency_mhz": int(cpu_freq.max) if cpu_freq else None,
                "usage_percent": cpu_percent
            })

            hardware = HardwareState(
                snapshot_id=snapshot_id,
                component_type="cpu",
                component_data=component_data
            )

            self.db.create_hardware_state(hardware)
            self.log_info(f"Recorded CPU: {cpu_count} cores @ {cpu_freq.current if cpu_freq else 'N/A'}MHz")
            return True

        except Exception as e:
            self.log_error(f"Failed to collect CPU data: {e}")
            return False

    def _collect_memory(self, snapshot_id: int) -> bool:
        """Collect memory information using psutil"""
        if not psutil:
            self.log_warning("psutil not installed, skipping memory collection")
            return False

        try:
            mem = psutil.virtual_memory()

            component_data = json.dumps({
                "total_gb": round(mem.total / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
                "used_gb": round(mem.used / (1024**3), 2),
                "percent_used": mem.percent,
                "percent_available": 100 - mem.percent
            })

            hardware = HardwareState(
                snapshot_id=snapshot_id,
                component_type="memory",
                component_data=component_data
            )

            self.db.create_hardware_state(hardware)
            self.log_info(f"Recorded Memory: {mem.total / (1024**3):.1f}GB total, {mem.percent}% used")
            return True

        except Exception as e:
            self.log_error(f"Failed to collect memory data: {e}")
            return False
