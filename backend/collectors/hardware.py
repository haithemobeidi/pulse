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

try:
    import winreg
except ImportError:
    winreg = None

try:
    from pynvml import *
    nvml_available = True
except ImportError:
    nvml_available = False

# Known GPU VRAM amounts (fallback when WMI returns invalid)
KNOWN_GPU_VRAM_GB = {
    "nvidia geforce rtx 5090": 32,
    "nvidia geforce rtx 6000": 24,
    "nvidia geforce rtx 4090": 24,
    "nvidia geforce rtx 4080": 16,
    "nvidia geforce rtx 4070": 12,
    "amd radeon rx 7900 xtx": 24,
    "amd radeon rx 7900 xt": 20,
    "intel arc a770": 16,
}


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
                adapter_ram = vc.AdapterRAM

                # Get driver version
                driver_version = vc.DriverVersion

                # For NVIDIA, get the user-facing driver version (e.g., "591.74")
                # WMI gives the internal format like "32.0.15.9174"
                if "nvidia" in gpu_name.lower():
                    nvidia_version = self._get_nvidia_driver_version()
                    if nvidia_version:
                        self.log_info(f"Got NVIDIA user-facing driver version: {nvidia_version}")
                        driver_version = nvidia_version
                    elif driver_version and '.' in driver_version:
                        # Convert WMI format to user-facing: "32.0.15.9174" → "591.74"
                        converted = self._convert_wmi_driver_version(driver_version)
                        if converted:
                            self.log_info(f"Converted WMI version {driver_version} → {converted}")
                            driver_version = converted
                        else:
                            self.log_warning(f"Could not convert NVIDIA driver version, using WMI format: {driver_version}")

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
            self.log_info(f"VRAM bytes from WMI: {vram_bytes}")

            vram_mb = None

            # Try to get VRAM from bytes first
            if vram_bytes and vram_bytes > 0:
                vram_mb = int(vram_bytes) // (1024 * 1024)
                self.log_info(f"Got VRAM from WMI: {vram_mb}MB")
            else:
                # Try known GPU database
                gpu_name_lower = gpu_to_record['name'].lower()
                for known_gpu, known_vram_gb in KNOWN_GPU_VRAM_GB.items():
                    if known_gpu in gpu_name_lower:
                        vram_mb = known_vram_gb * 1024
                        self.log_info(f"Got VRAM from known database: {vram_mb}MB ({known_vram_gb}GB)")
                        break

            # If still no VRAM, try registry
            if not vram_mb:
                vram_mb = self._get_gpu_vram_from_registry(gpu_to_record['name'])
                if vram_mb:
                    self.log_info(f"Got VRAM from registry: {vram_mb}MB")

            # Try to get GPU metrics using NVIDIA Management Library (pynvml)
            vram_used_mb = None
            temperature_c = None
            gpu_load = None

            if nvml_available and "nvidia" in gpu_to_record['name'].lower():
                try:
                    nvmlInit()
                    device_count = nvmlDeviceGetCount()
                    self.log_info(f"NVIDIA devices found: {device_count}")

                    if device_count > 0:
                        handle = nvmlDeviceGetHandleByIndex(0)
                        mem_info = nvmlDeviceGetMemoryInfo(handle)
                        vram_used_mb = mem_info.used // (1024 * 1024)

                        try:
                            temperature_c = nvmlDeviceGetTemperature(handle, 0)
                        except Exception as e:
                            self.log_warning(f"Could not get GPU temperature: {e}")

                        self.log_info(f"GPU Memory: {vram_used_mb}MB used")
                        self.log_info(f"GPU Temperature: {temperature_c}°C")

                    nvmlShutdown()
                except Exception as e:
                    self.log_warning(f"pynvml failed: {e}")

            self.log_info(f"Creating GPU state: name={gpu_to_record['name']}, driver={gpu_to_record['driver']}, vram_total={vram_mb}MB, vram_used={vram_used_mb}MB, temp={temperature_c}°C")

            gpu_state = GPUState(
                snapshot_id=snapshot_id,
                gpu_name=gpu_to_record['name'],
                driver_version=gpu_to_record['driver'],
                vram_total_mb=vram_mb,
                vram_used_mb=vram_used_mb,
                temperature_c=temperature_c,
                power_draw_w=None,  # pynvml doesn't provide power easily
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

    def _convert_wmi_driver_version(self, wmi_version: str) -> str:
        """
        Convert WMI internal driver version to user-facing NVIDIA format.

        WMI format: "32.0.15.9174" → take last two parts "15" and "9174"
        → combine as "591.74" (last 5 digits of concatenated string, split at 3)

        The conversion: take last 5 digits of the combined last two parts,
        insert a dot after the 3rd digit.
        Example: "15" + "9174" = "159174" → last 5 = "59174" → "591.74"

        Args:
            wmi_version: WMI format version string (e.g., "32.0.15.9174")

        Returns:
            User-facing version (e.g., "591.74") or None if conversion fails
        """
        try:
            parts = wmi_version.split('.')
            if len(parts) >= 4:
                # Take last two parts and concatenate
                combined = parts[-2] + parts[-1]
                # Take last 5 digits
                if len(combined) >= 5:
                    last5 = combined[-5:]
                    # Insert dot after 3rd digit: "59174" → "591.74"
                    return f"{last5[:3]}.{last5[3:]}"
        except Exception as e:
            self.log_warning(f"WMI version conversion failed: {e}")
        return None

    def _get_nvidia_driver_version(self) -> str:
        """
        Get NVIDIA user-facing driver version (e.g., "591.86").

        Tries nvidia-smi first (most reliable), then falls back to registry.

        Returns:
            Driver version string (e.g., "591.86") or None
        """
        # Method 1: Try nvidia-smi command (most reliable for user-facing version)
        try:
            import subprocess
            self.log_info("Attempting to get NVIDIA driver version from nvidia-smi...")

            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                version = result.stdout.strip()
                if version:
                    self.log_info(f"Got NVIDIA driver version from nvidia-smi: {version}")
                    return version
        except FileNotFoundError:
            self.log_info("nvidia-smi not found, falling back to registry...")
        except Exception as e:
            self.log_warning(f"nvidia-smi failed: {e}, falling back to registry...")

        # Method 2: Fall back to registry lookup
        self.log_info("Looking up NVIDIA driver version from registry...")

        try:
            import winreg

            # Registry paths that might contain NVIDIA driver version
            registry_paths = [
                # NVIDIA Control Panel current driver
                (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\nvlddmkm"),
                # NVIDIA ForceWare registry
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\NVIDIA Corporation\Global\GFXDevice"),
                # NVIDIA driver version via installer
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\NVIDIA Corporation\NvCleanInstall"),
                # Direct display adapter path
                (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Class\{4D36E968-E325-11CE-BFC1-08002BE10318}"),
            ]

            for hkey, path in registry_paths:
                try:
                    self.log_info(f"Checking registry path: {path}")
                    reg = winreg.ConnectRegistry(None, hkey)
                    key = winreg.OpenKey(reg, path)

                    # Try multiple value names that might contain version
                    value_names = ["DriverVersion", "Version", "ImageVersion", "InstalledVersion"]

                    for value_name in value_names:
                        try:
                            value, value_type = winreg.QueryValueEx(key, value_name)
                            self.log_info(f"  Found {value_name}: {value}")

                            # Check if this looks like a driver version (e.g., 579.01 or 32.0.15.9174)
                            if value and isinstance(value, str):
                                # If it's the long form (32.0.15.9174), try to extract the driver number
                                parts = value.split('.')
                                if len(parts) >= 2:
                                    # Try to get the major version number (usually first 2-3 parts)
                                    if parts[0].isdigit() and int(parts[0]) < 100:
                                        # Short form like 579.01 or 32.0
                                        return value
                                    elif parts[0].isdigit() and int(parts[0]) > 100:
                                        # Likely a full version number
                                        return value

                        except OSError:
                            pass

                    winreg.CloseKey(key)
                    reg.CloseKey()

                except Exception as e:
                    self.log_info(f"  Path not found or error: {e}")

            # If we got here, try one more thing - look for version in all subkeys under the device class
            self.log_info("Attempting detailed search in device class registry...")
            try:
                reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
                class_key = r"SYSTEM\CurrentControlSet\Control\Class\{4D36E968-E325-11CE-BFC1-08002BE10318}"
                key = winreg.OpenKey(reg, class_key)

                # Enumerate all subkeys
                for i in range(winreg.QueryInfoKey(key)[0]):
                    subkey_name = winreg.EnumKey(key, i)
                    self.log_info(f"  Checking subkey: {subkey_name}")

                    subkey = winreg.OpenKey(key, subkey_name)
                    try:
                        # Get description to identify NVIDIA GPU
                        try:
                            desc = winreg.QueryValueEx(subkey, "DriverDesc")[0]
                            if "nvidia" in desc.lower():
                                self.log_info(f"    Found NVIDIA GPU: {desc}")

                                # Try to get version
                                try:
                                    version = winreg.QueryValueEx(subkey, "DriverVersion")[0]
                                    self.log_info(f"    DriverVersion value: {version}")
                                    if version:
                                        return version
                                except OSError:
                                    pass

                        except OSError:
                            pass
                    finally:
                        winreg.CloseKey(subkey)

                winreg.CloseKey(key)
                reg.CloseKey()

            except Exception as e:
                self.log_error(f"Detailed registry search failed: {e}")

        except Exception as e:
            self.log_error(f"NVIDIA driver version lookup failed: {e}")
            import traceback
            self.log_error(traceback.format_exc())

        return None

    def _get_gpu_vram_from_registry(self, gpu_name: str) -> int:
        """
        Try to get GPU VRAM from Windows registry.

        Registry path: HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Control\\Class\\{4D36E968-E325-11CE-BFC1-08002BE10318}

        Args:
            gpu_name: GPU name to look up

        Returns:
            VRAM in MB or None if not found
        """
        if not winreg:
            return None

        try:
            import winreg
            reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)

            # This is the GUID for display adapters
            display_class_key = r"SYSTEM\CurrentControlSet\Control\Class\{4D36E968-E325-11CE-BFC1-08002BE10318}"

            try:
                key = winreg.OpenKey(reg, display_class_key)

                # Enumerate subkeys (usually 0000, 0001, etc.)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name)

                    try:
                        # Get the device description
                        desc = winreg.QueryValueEx(subkey, "DriverDesc")[0]

                        # If this matches our GPU, try to get memory
                        if gpu_name.lower() in desc.lower():
                            # Try different registry value names for VRAM
                            for vram_key in ["HardwareInformation.qxDriverMemory", "HardwareInformation.MemorySize"]:
                                try:
                                    vram_bytes = winreg.QueryValueEx(subkey, vram_key)[0]
                                    if isinstance(vram_bytes, int) and vram_bytes > 0:
                                        vram_mb = vram_bytes // (1024 * 1024)
                                        self.log_info(f"Found {gpu_name} in registry: {vram_mb}MB")
                                        return vram_mb
                                except OSError:
                                    pass

                    finally:
                        winreg.CloseKey(subkey)

                winreg.CloseKey(key)

            except OSError as e:
                self.log_warning(f"Could not access registry display key: {e}")

            reg.CloseKey()

        except Exception as e:
            self.log_warning(f"Registry VRAM lookup failed: {e}")

        return None

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
