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

        # Collect motherboard data
        if self._collect_motherboard(snapshot_id):
            collected = True
            self.log_info("Motherboard data collected")

        # Collect storage drives
        if self._collect_storage(snapshot_id):
            collected = True
            self.log_info("Storage data collected")

        # Collect network adapters
        if self._collect_network(snapshot_id):
            collected = True
            self.log_info("Network data collected")

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
        """Collect CPU information using psutil + WMI"""
        if not psutil:
            self.log_warning("psutil not installed, skipping CPU collection")
            return False

        try:
            # Get CPU info from psutil
            cpu_count = psutil.cpu_count(logical=False)  # Physical cores
            cpu_count_logical = psutil.cpu_count(logical=True)  # Logical processors
            cpu_freq = psutil.cpu_freq()
            cpu_percent = psutil.cpu_percent(interval=1)

            # Get CPU name/brand from WMI
            cpu_name = None
            cpu_manufacturer = None
            cpu_architecture = None
            cpu_socket = None
            cpu_l2_cache_kb = None
            cpu_l3_cache_kb = None
            if wmi:
                try:
                    c = wmi.WMI()
                    processors = c.Win32_Processor()
                    if processors:
                        p = processors[0]
                        cpu_name = p.Name.strip() if p.Name else None
                        cpu_manufacturer = p.Manufacturer
                        cpu_socket = p.SocketDesignation
                        cpu_l2_cache_kb = p.L2CacheSize
                        cpu_l3_cache_kb = p.L3CacheSize
                        # Architecture: 0=x86, 9=x64, 12=ARM64
                        arch_map = {0: "x86", 9: "x64", 5: "ARM", 12: "ARM64"}
                        cpu_architecture = arch_map.get(p.Architecture, f"Unknown ({p.Architecture})")
                        self.log_info(f"WMI CPU: {cpu_name}")
                except Exception as e:
                    self.log_warning(f"WMI CPU query failed: {e}")

            component_data = json.dumps({
                "name": cpu_name,
                "manufacturer": cpu_manufacturer,
                "architecture": cpu_architecture,
                "socket": cpu_socket,
                "physical_cores": cpu_count,
                "logical_processors": cpu_count_logical,
                "frequency_mhz": int(cpu_freq.current) if cpu_freq else None,
                "max_frequency_mhz": int(cpu_freq.max) if cpu_freq else None,
                "l2_cache_kb": cpu_l2_cache_kb,
                "l3_cache_mb": round(cpu_l3_cache_kb / 1024, 1) if cpu_l3_cache_kb else None,
                "usage_percent": cpu_percent
            })

            hardware = HardwareState(
                snapshot_id=snapshot_id,
                component_type="cpu",
                component_data=component_data
            )

            self.db.create_hardware_state(hardware)
            self.log_info(f"Recorded CPU: {cpu_name or 'Unknown'} ({cpu_count} cores @ {cpu_freq.current if cpu_freq else 'N/A'}MHz)")
            return True

        except Exception as e:
            self.log_error(f"Failed to collect CPU data: {e}")
            return False

    def _collect_memory(self, snapshot_id: int) -> bool:
        """Collect memory information using psutil + WMI"""
        if not psutil:
            self.log_warning("psutil not installed, skipping memory collection")
            return False

        try:
            mem = psutil.virtual_memory()

            # Get detailed RAM stick info from WMI
            sticks = []
            total_slots = None
            memory_type_name = None
            if wmi:
                try:
                    c = wmi.WMI()
                    # Get individual RAM sticks
                    for stick in c.Win32_PhysicalMemory():
                        speed = stick.ConfiguredClockSpeed or stick.Speed
                        capacity_gb = round(int(stick.Capacity or 0) / (1024**3), 1) if stick.Capacity else None
                        # Memory type: 26=DDR4, 34=DDR5
                        mem_type_map = {20: "DDR", 21: "DDR2", 22: "DDR2", 24: "DDR3", 26: "DDR4", 34: "DDR5"}
                        mem_type = mem_type_map.get(stick.SMBIOSMemoryType, f"Type {stick.SMBIOSMemoryType}")
                        if not memory_type_name:
                            memory_type_name = mem_type

                        # Build slot label from BankLabel + DeviceLocator
                        bank = (stick.BankLabel or "").strip()
                        locator = (stick.DeviceLocator or "").strip()
                        if bank and locator and bank != locator:
                            slot_label = f"{bank} / {locator}"
                        elif bank:
                            slot_label = bank
                        elif locator:
                            slot_label = locator
                        else:
                            slot_label = f"Slot {len(sticks) + 1}"

                        # Deduplicate: if this label already used, add index
                        existing_labels = [s['slot'] for s in sticks]
                        if slot_label in existing_labels:
                            slot_label = f"{slot_label} (#{len(sticks) + 1})"

                        stick_info = {
                            "manufacturer": (stick.Manufacturer or "").strip(),
                            "part_number": (stick.PartNumber or "").strip(),
                            "serial": (stick.SerialNumber or "").strip(),
                            "capacity_gb": capacity_gb,
                            "speed_mhz": speed,
                            "type": mem_type,
                            "slot": slot_label,
                            "form_factor": {8: "DIMM", 12: "SO-DIMM"}.get(stick.FormFactor, f"Type {stick.FormFactor}")
                        }
                        sticks.append(stick_info)
                        self.log_info(f"RAM Stick: {stick_info['manufacturer']} {stick_info['part_number']} {capacity_gb}GB {mem_type}-{speed}MHz ({slot_label})")

                    # Get total slot count
                    for array in c.Win32_PhysicalMemoryArray():
                        total_slots = array.MemoryDevices
                except Exception as e:
                    self.log_warning(f"WMI memory query failed: {e}")

            component_data = json.dumps({
                "total_gb": round(mem.total / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
                "used_gb": round(mem.used / (1024**3), 2),
                "percent_used": mem.percent,
                "percent_available": 100 - mem.percent,
                "memory_type": memory_type_name,
                "sticks": sticks,
                "slots_used": len(sticks),
                "slots_total": total_slots
            })

            hardware = HardwareState(
                snapshot_id=snapshot_id,
                component_type="memory",
                component_data=component_data
            )

            self.db.create_hardware_state(hardware)
            self.log_info(f"Recorded Memory: {mem.total / (1024**3):.1f}GB total ({len(sticks)} sticks), {mem.percent}% used")
            return True

        except Exception as e:
            self.log_error(f"Failed to collect memory data: {e}")
            return False

    def _collect_motherboard(self, snapshot_id: int) -> bool:
        """Collect motherboard info using WMI"""
        if not wmi:
            return False

        try:
            c = wmi.WMI()

            # Win32_BaseBoard = motherboard
            boards = c.Win32_BaseBoard()
            board = boards[0] if boards else None

            # Win32_BIOS = BIOS info
            bioses = c.Win32_BIOS()
            bios = bioses[0] if bioses else None

            if not board and not bios:
                return False

            # Filter out junk placeholder values from WMI
            def clean(val):
                if not val:
                    return None
                v = val.strip()
                junk = ["default string", "default", "x.x", "n/a", "na", "none", "to be filled", "not specified", "chassis serial number", "system serial number"]
                if v.lower() in junk or not v:
                    return None
                return v

            component_data = json.dumps({
                "manufacturer": clean(board.Manufacturer) if board else None,
                "product": clean(board.Product) if board else None,
                "version": clean(board.Version) if board else None,
                "serial": clean(board.SerialNumber) if board else None,
                "bios_vendor": clean(bios.Manufacturer) if bios else None,
                "bios_version": clean(bios.SMBIOSBIOSVersion) if bios else None,
                "bios_date": (bios.ReleaseDate or "").split(".")[0] if bios and bios.ReleaseDate else None,
            })

            hardware = HardwareState(
                snapshot_id=snapshot_id,
                component_type="motherboard",
                component_data=component_data
            )

            self.db.create_hardware_state(hardware)
            name = f"{board.Manufacturer} {board.Product}" if board else "Unknown"
            self.log_info(f"Recorded Motherboard: {name}")
            return True

        except Exception as e:
            self.log_error(f"Failed to collect motherboard data: {e}")
            return False

    def _collect_storage(self, snapshot_id: int) -> bool:
        """Collect storage drive info using WMI + psutil"""
        try:
            drives = []

            # Get physical disk info from WMI
            if wmi:
                try:
                    c = wmi.WMI()
                    for disk in c.Win32_DiskDrive():
                        size_gb = round(int(disk.Size or 0) / (1024**3), 1) if disk.Size else None
                        media_type = (disk.MediaType or "").strip()
                        # Detect NVMe/SSD from model name or interface
                        interface = (disk.InterfaceType or "").strip()
                        model = (disk.Model or "").strip()

                        model_lower = model.lower()
                        # Known NVMe/SSD model keywords (check before media_type fallback)
                        nvme_keywords = ["nvme", "mp600", "mp700", "980 pro", "970 evo", "sn850",
                                         "sn770", "a80", "p5 plus", "firecuda", "rocket", "wd_black"]
                        ssd_keywords = ["ssd", "sandisk", "crucial", "samsung ssd", "wd blue sa",
                                        "kingston", "inland", "adata"]

                        drive_type = "Unknown"
                        if any(kw in model_lower for kw in nvme_keywords) or "nvme" in interface.lower():
                            drive_type = "NVMe SSD"
                        elif any(kw in model_lower for kw in ssd_keywords) or "solid" in media_type.lower():
                            drive_type = "SSD"
                        elif "hdd" in model_lower or any(kw in model_lower for kw in ["barracuda", "ironwolf", "caviar", "toshiba dt", "toshiba hdw"]):
                            drive_type = "HDD"
                        elif "fixed" in media_type.lower():
                            # Fallback: WMI says "Fixed hard disk media" for everything
                            # Assume SSD if interface is SCSI/IDE (modern NVMe/SATA show as these)
                            drive_type = "SSD"

                        drives.append({
                            "model": model,
                            "serial": (disk.SerialNumber or "").strip(),
                            "size_gb": size_gb,
                            "interface": interface,
                            "drive_type": drive_type,
                            "firmware": (disk.FirmwareRevision or "").strip(),
                        })
                        self.log_info(f"Drive: {model} ({size_gb}GB, {drive_type}, {interface})")
                except Exception as e:
                    self.log_warning(f"WMI disk query failed: {e}")

            # Get partition usage from psutil
            partitions = []
            if psutil:
                for part in psutil.disk_partitions(all=False):
                    try:
                        usage = psutil.disk_usage(part.mountpoint)
                        partitions.append({
                            "mount": part.mountpoint,
                            "fstype": part.fstype,
                            "total_gb": round(usage.total / (1024**3), 1),
                            "used_gb": round(usage.used / (1024**3), 1),
                            "free_gb": round(usage.free / (1024**3), 1),
                            "percent_used": usage.percent,
                        })
                    except (PermissionError, OSError):
                        pass

            if not drives and not partitions:
                return False

            component_data = json.dumps({
                "drives": drives,
                "partitions": partitions,
            })

            hardware = HardwareState(
                snapshot_id=snapshot_id,
                component_type="storage",
                component_data=component_data
            )

            self.db.create_hardware_state(hardware)
            self.log_info(f"Recorded Storage: {len(drives)} drive(s), {len(partitions)} partition(s)")
            return True

        except Exception as e:
            self.log_error(f"Failed to collect storage data: {e}")
            return False

    def _collect_network(self, snapshot_id: int) -> bool:
        """Collect network adapter info using WMI"""
        if not wmi:
            return False

        try:
            c = wmi.WMI()
            adapters = []

            for nic in c.Win32_NetworkAdapter(PhysicalAdapter=True):
                # Get IP config for this adapter
                speed_mbps = None
                if nic.Speed:
                    try:
                        speed_mbps = round(int(nic.Speed) / 1_000_000)
                    except (ValueError, TypeError):
                        pass

                adapters.append({
                    "name": (nic.Name or "").strip(),
                    "manufacturer": (nic.Manufacturer or "").strip(),
                    "mac_address": nic.MACAddress,
                    "speed_mbps": speed_mbps,
                    "type": (nic.AdapterType or "").strip(),
                    "status": "Connected" if nic.NetConnectionStatus == 2 else "Disconnected",
                    "connection_name": (nic.NetConnectionID or "").strip(),
                })

            if not adapters:
                return False

            component_data = json.dumps({"adapters": adapters})

            hardware = HardwareState(
                snapshot_id=snapshot_id,
                component_type="network",
                component_data=component_data
            )

            self.db.create_hardware_state(hardware)
            self.log_info(f"Recorded Network: {len(adapters)} adapter(s)")
            return True

        except Exception as e:
            self.log_error(f"Failed to collect network data: {e}")
            return False
