"""Data collectors for PC-Inspector"""

from backend.collectors.hardware import HardwareCollector
from backend.collectors.monitors import MonitorCollector

__all__ = [
    "HardwareCollector",
    "MonitorCollector",
]
