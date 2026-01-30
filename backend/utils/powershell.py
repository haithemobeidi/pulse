"""
PowerShell Bridge for Windows System Queries from WSL2

Enables WSL2 to execute PowerShell commands on the host Windows system
and return parsed JSON results. This allows PC-Inspector to collect
comprehensive Windows system information from a Linux environment.

Usage:
    from backend.utils.powershell import run_powershell

    result = run_powershell('Get-WmiObject Win32_VideoController | ConvertTo-Json')
    gpu_info = json.loads(result)
"""

import subprocess
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PowerShellError(Exception):
    """Raised when PowerShell command fails"""
    pass


def run_powershell(command: str, timeout: int = 30) -> str:
    """
    Execute PowerShell command from WSL2 and return output.

    Args:
        command: PowerShell command to execute
        timeout: Seconds to wait before timing out

    Returns:
        Raw PowerShell output (JSON format expected)

    Raises:
        PowerShellError: If command fails
    """
    try:
        # Execute PowerShell command
        # Note: Using powershell.exe from WSL2 which calls Windows PowerShell
        full_cmd = f'powershell.exe -Command "{command}"'

        result = subprocess.run(
            full_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout
            logger.error(f"PowerShell error: {error_msg}")
            raise PowerShellError(f"PowerShell command failed: {error_msg}")

        return result.stdout.strip()

    except subprocess.TimeoutExpired:
        raise PowerShellError(f"PowerShell command timed out after {timeout}s")
    except Exception as e:
        logger.error(f"PowerShell execution error: {e}")
        raise PowerShellError(f"Failed to execute PowerShell command: {e}")


def run_powershell_json(command: str, timeout: int = 30) -> Any:
    """
    Execute PowerShell command and parse JSON output.

    Args:
        command: PowerShell command returning JSON
        timeout: Seconds to wait before timing out

    Returns:
        Parsed JSON result (dict, list, or primitive type)

    Raises:
        PowerShellError: If command fails or JSON parsing fails
    """
    try:
        output = run_powershell(command, timeout)

        if not output:
            return None

        # Parse JSON
        try:
            return json.loads(output)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse PowerShell JSON output: {output}")
            raise PowerShellError(f"Invalid JSON from PowerShell: {e}")

    except PowerShellError:
        raise


# ============================================================================
# Windows System Query Functions
# ============================================================================

def get_gpu_info() -> List[Dict[str, Any]]:
    """
    Get GPU information using WMI.

    Returns:
        List of GPU dictionaries with: Name, DriverVersion, AdapterRAM, etc.
    """
    command = """
    Get-WmiObject Win32_VideoController |
    Select-Object Name, DriverVersion, AdapterRAM, Status |
    ConvertTo-Json -AsArray
    """

    try:
        result = run_powershell_json(command)
        # Ensure result is a list
        if isinstance(result, dict):
            return [result]
        return result or []
    except PowerShellError as e:
        logger.error(f"Failed to get GPU info: {e}")
        return []


def get_monitor_info() -> List[Dict[str, Any]]:
    """
    Get monitor information from PnP devices.

    Returns:
        List of monitor dictionaries with: FriendlyName, Status, InstanceId
    """
    command = """
    Get-PnpDevice -Class Monitor |
    Select-Object FriendlyName, Status, InstanceId |
    ConvertTo-Json -AsArray
    """

    try:
        result = run_powershell_json(command)
        # Ensure result is a list
        if isinstance(result, dict):
            return [result]
        return result or []
    except PowerShellError as e:
        logger.error(f"Failed to get monitor info: {e}")
        return []


def get_display_driver_version() -> Optional[str]:
    """
    Get NVIDIA/AMD display driver version from registry.

    Returns:
        Driver version string (e.g., "591.74") or None
    """
    command = """
    $nvidia = Get-ItemProperty -Path "Registry::HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Control\\Class\\{4D36E968-E325-11CE-BFC1-08002BE10318}\\0000" -Name "DriverVersion" -ErrorAction SilentlyContinue
    if ($nvidia) { $nvidia.DriverVersion }
    else {
        $amd = Get-ItemProperty -Path "Registry::HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Control\\Class\\{4D36E968-E325-11CE-BFC1-08002BE10318}\\0001" -Name "DriverVersion" -ErrorAction SilentlyContinue
        if ($amd) { $amd.DriverVersion }
    }
    """

    try:
        result = run_powershell(command)
        return result if result else None
    except PowerShellError as e:
        logger.warning(f"Could not retrieve driver version: {e}")
        return None


def get_system_info() -> Dict[str, Any]:
    """
    Get basic system information.

    Returns:
        Dictionary with: ComputerName, OSVersion, Manufacturer, Model, TotalPhysicalMemory
    """
    command = """
    Get-WmiObject Win32_ComputerSystem |
    Select-Object Name, Manufacturer, Model, SystemFamily, TotalPhysicalMemory |
    ConvertTo-Json
    """

    try:
        return run_powershell_json(command) or {}
    except PowerShellError as e:
        logger.error(f"Failed to get system info: {e}")
        return {}


def get_cpu_info() -> Dict[str, Any]:
    """
    Get CPU information.

    Returns:
        Dictionary with: Name, Cores, LogicalProcessors, MaxClockSpeed
    """
    command = """
    Get-WmiObject Win32_Processor |
    Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed |
    ConvertTo-Json
    """

    try:
        result = run_powershell_json(command)
        # Take first CPU if multiple
        if isinstance(result, list):
            return result[0] if result else {}
        return result or {}
    except PowerShellError as e:
        logger.error(f"Failed to get CPU info: {e}")
        return {}


def get_memory_info() -> Dict[str, Any]:
    """
    Get memory/RAM information.

    Returns:
        Dictionary with: TotalVisibleMemorySize, FreePhysicalMemory
    """
    command = """
    Get-WmiObject Win32_OperatingSystem |
    Select-Object TotalVisibleMemorySize, FreePhysicalMemory |
    ConvertTo-Json
    """

    try:
        return run_powershell_json(command) or {}
    except PowerShellError as e:
        logger.error(f"Failed to get memory info: {e}")
        return {}


def get_installed_software() -> List[Dict[str, Any]]:
    """
    Get list of installed software from registry.

    Returns:
        List of software dictionaries with: DisplayName, DisplayVersion
    """
    command = """
    Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* |
    Where-Object { $_.DisplayName -ne $null } |
    Select-Object DisplayName, DisplayVersion, InstallDate |
    ConvertTo-Json -AsArray
    """

    try:
        result = run_powershell_json(command)
        if isinstance(result, dict):
            return [result]
        return result or []
    except PowerShellError as e:
        logger.warning(f"Failed to get installed software: {e}")
        return []


def get_event_log_errors(hours: int = 24) -> List[Dict[str, Any]]:
    """
    Get recent error events from Windows Event Log.

    Args:
        hours: Look back this many hours for events

    Returns:
        List of event dictionaries with: TimeCreated, ProviderName, Message
    """
    command = f"""
    $after = (Get-Date).AddHours(-{hours})
    Get-WinEvent -FilterHashtable @{{
        LogName='System'
        Level=2,3
        StartTime=$after
    }} -ErrorAction SilentlyContinue |
    Select-Object TimeCreated, ProviderName, Message -First 50 |
    ConvertTo-Json -AsArray
    """

    try:
        result = run_powershell_json(command)
        if isinstance(result, dict):
            return [result]
        return result or []
    except PowerShellError as e:
        logger.warning(f"Failed to get event log: {e}")
        return []


def get_gpu_temperature() -> Optional[float]:
    """
    Attempt to get GPU temperature.

    Note: This requires NVIDIA/AMD utilities or WMI support.
    May return None if not available on system.

    Returns:
        Temperature in Celsius or None
    """
    # Try NVIDIA first
    command = """
    try {
        $nvidia = Get-WmiObject -Namespace "root\\cimv2" -Class Win32_VideoController -ErrorAction SilentlyContinue
        if ($nvidia -and $nvidia.CurrentTemperature) {
            # Temperature from WMI (if available)
            [int]$nvidia.CurrentTemperature / 100
        }
    } catch {}
    """

    try:
        result = run_powershell(command)
        if result:
            return float(result)
    except (PowerShellError, ValueError):
        pass

    return None


# ============================================================================
# Health Check
# ============================================================================

def test_connection() -> bool:
    """
    Test PowerShell bridge connectivity.

    Returns:
        True if PowerShell is accessible and working
    """
    try:
        result = run_powershell('echo "test"')
        return result == "test"
    except PowerShellError:
        return False
