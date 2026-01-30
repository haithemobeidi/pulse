"""
SQLite Database Schema and Models

Defines all tables for PC-Inspector system monitoring and tracks:
- System snapshots (periodic captures of hardware state)
- GPU and monitor configuration
- User-logged issues
- Hardware and driver tracking
- Windows event logs
- Configuration changes over time
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum

# Database file location
DB_PATH = Path(__file__).parent.parent / "data" / "system.db"


class SnapshotType(str, Enum):
    """Types of system snapshots"""
    SCHEDULED = "scheduled"
    ISSUE_LOGGED = "issue_logged"
    MANUAL = "manual"


class IssueType(str, Enum):
    """Categories of issues that can be logged"""
    MONITOR_BLACKOUT = "monitor_blackout"
    CRASH = "crash"
    PERFORMANCE = "performance"
    DRIVER_ISSUE = "driver_issue"
    POWER = "power"
    OTHER = "other"


class IssueSeverity(str, Enum):
    """Severity levels for issues"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================================================
# Pydantic Models for Request/Response Validation
# ============================================================================

@dataclass
class Snapshot:
    """System state capture at a point in time"""
    id: Optional[int] = None
    timestamp: Optional[str] = None
    snapshot_type: str = SnapshotType.MANUAL
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GPUState:
    """GPU information captured in a snapshot"""
    id: Optional[int] = None
    snapshot_id: int = None
    gpu_name: str = None
    driver_version: str = None
    vram_total_mb: int = None
    vram_used_mb: int = None
    temperature_c: Optional[float] = None
    power_draw_w: Optional[float] = None
    clock_speed_mhz: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class MonitorState:
    """Monitor configuration captured in a snapshot"""
    id: Optional[int] = None
    snapshot_id: int = None
    monitor_name: str = None
    connection_type: str = None  # DisplayPort, HDMI, VGA, etc.
    resolution: Optional[str] = None
    refresh_rate_hz: Optional[int] = None
    status: str = "connected"  # connected, disconnected
    pnp_device_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Issue:
    """User-logged problem or anomaly"""
    id: Optional[int] = None
    snapshot_id: int = None
    issue_type: str = IssueType.OTHER
    description: str = None
    severity: str = IssueSeverity.MEDIUM
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class HardwareState:
    """General hardware component tracking"""
    id: Optional[int] = None
    snapshot_id: int = None
    component_type: str = None  # cpu, memory, motherboard, storage
    component_data: Optional[str] = None  # JSON string

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class InstalledSoftware:
    """Installed software tracking"""
    id: Optional[int] = None
    snapshot_id: int = None
    software_name: str = None
    version: Optional[str] = None
    install_date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class SystemEvent:
    """Windows Event Log entries"""
    id: Optional[int] = None
    snapshot_id: int = None
    event_type: str = None
    event_source: str = None
    description: str = None
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ConfigChange:
    """Detected configuration changes"""
    id: Optional[int] = None
    snapshot_id: int = None
    change_type: str = None  # driver_update, software_install, setting_change
    component: str = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


# ============================================================================
# Database Connection and Management
# ============================================================================

class Database:
    """SQLite database interface for PC-Inspector"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = None

    def connect(self):
        """Establish database connection"""
        # check_same_thread=False allows connection to be used from different threads
        # Safe for this local single-user application
        self.connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        return self.connection

    def disconnect(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a query and return cursor"""
        if not self.connection:
            self.connect()
        return self.connection.execute(query, params)

    def commit(self):
        """Commit transaction"""
        if self.connection:
            self.connection.commit()

    def create_schema(self):
        """Create all database tables"""
        if not self.connection:
            self.connect()

        schema_sql = """
        -- Snapshots: Point-in-time system captures
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            snapshot_type TEXT NOT NULL CHECK(snapshot_type IN ('scheduled', 'issue_logged', 'manual')),
            notes TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON snapshots(timestamp);
        CREATE INDEX IF NOT EXISTS idx_snapshots_type ON snapshots(snapshot_type);

        -- GPU State: Video card information
        CREATE TABLE IF NOT EXISTS gpu_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL UNIQUE,
            gpu_name TEXT NOT NULL,
            driver_version TEXT,
            vram_total_mb INTEGER,
            vram_used_mb INTEGER,
            temperature_c REAL,
            power_draw_w REAL,
            clock_speed_mhz INTEGER,
            FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_gpu_state_snapshot ON gpu_state(snapshot_id);
        CREATE INDEX IF NOT EXISTS idx_gpu_state_driver ON gpu_state(driver_version);

        -- Monitor State: Monitor configuration and connection
        CREATE TABLE IF NOT EXISTS monitor_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            monitor_name TEXT NOT NULL,
            connection_type TEXT,
            resolution TEXT,
            refresh_rate_hz INTEGER,
            status TEXT DEFAULT 'connected',
            pnp_device_id TEXT,
            FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_monitor_state_snapshot ON monitor_state(snapshot_id);
        CREATE INDEX IF NOT EXISTS idx_monitor_state_connection ON monitor_state(connection_type);

        -- Issues: User-logged problems
        CREATE TABLE IF NOT EXISTS issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            issue_type TEXT NOT NULL CHECK(issue_type IN ('monitor_blackout', 'crash', 'performance', 'driver_issue', 'power', 'other')),
            description TEXT,
            severity TEXT DEFAULT 'medium' CHECK(severity IN ('low', 'medium', 'high', 'critical')),
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_issues_snapshot ON issues(snapshot_id);
        CREATE INDEX IF NOT EXISTS idx_issues_timestamp ON issues(timestamp);
        CREATE INDEX IF NOT EXISTS idx_issues_type ON issues(issue_type);

        -- Hardware State: CPU, RAM, motherboard tracking
        CREATE TABLE IF NOT EXISTS hardware_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            component_type TEXT NOT NULL,
            component_data TEXT,
            FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_hardware_state_snapshot ON hardware_state(snapshot_id);
        CREATE INDEX IF NOT EXISTS idx_hardware_state_component ON hardware_state(component_type);

        -- Installed Software: Software inventory
        CREATE TABLE IF NOT EXISTS installed_software (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            software_name TEXT NOT NULL,
            version TEXT,
            install_date TEXT,
            FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_software_snapshot ON installed_software(snapshot_id);
        CREATE INDEX IF NOT EXISTS idx_software_name ON installed_software(software_name);

        -- System Events: Windows Event Log entries
        CREATE TABLE IF NOT EXISTS system_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            event_source TEXT,
            description TEXT,
            timestamp DATETIME,
            FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_system_events_snapshot ON system_events(snapshot_id);
        CREATE INDEX IF NOT EXISTS idx_system_events_type ON system_events(event_type);

        -- Config Changes: Detected changes over time
        CREATE TABLE IF NOT EXISTS config_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            change_type TEXT NOT NULL,
            component TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_config_changes_snapshot ON config_changes(snapshot_id);
        CREATE INDEX IF NOT EXISTS idx_config_changes_component ON config_changes(component);
        """

        # Execute schema creation
        self.connection.executescript(schema_sql)
        self.commit()

    # ========================================================================
    # CRUD Operations
    # ========================================================================

    def create_snapshot(self, snapshot: Snapshot) -> int:
        """Create a new snapshot and return its ID"""
        cursor = self.execute(
            """
            INSERT INTO snapshots (snapshot_type, notes)
            VALUES (?, ?)
            """,
            (snapshot.snapshot_type, snapshot.notes)
        )
        self.commit()
        return cursor.lastrowid

    def get_snapshot(self, snapshot_id: int) -> Optional[Dict[str, Any]]:
        """Get snapshot by ID"""
        cursor = self.execute(
            "SELECT * FROM snapshots WHERE id = ?",
            (snapshot_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_snapshots(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get list of snapshots with pagination"""
        cursor = self.execute(
            """
            SELECT * FROM snapshots
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset)
        )
        return [dict(row) for row in cursor.fetchall()]

    def create_gpu_state(self, gpu: GPUState) -> int:
        """Create GPU state record for snapshot"""
        cursor = self.execute(
            """
            INSERT INTO gpu_state
            (snapshot_id, gpu_name, driver_version, vram_total_mb, vram_used_mb,
             temperature_c, power_draw_w, clock_speed_mhz)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (gpu.snapshot_id, gpu.gpu_name, gpu.driver_version, gpu.vram_total_mb,
             gpu.vram_used_mb, gpu.temperature_c, gpu.power_draw_w, gpu.clock_speed_mhz)
        )
        self.commit()
        return cursor.lastrowid

    def get_gpu_state(self, snapshot_id: int) -> Optional[Dict[str, Any]]:
        """Get GPU state for a snapshot"""
        cursor = self.execute(
            "SELECT * FROM gpu_state WHERE snapshot_id = ?",
            (snapshot_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_monitor_state(self, monitor: MonitorState) -> int:
        """Create monitor state record for snapshot"""
        cursor = self.execute(
            """
            INSERT INTO monitor_state
            (snapshot_id, monitor_name, connection_type, resolution, refresh_rate_hz, status, pnp_device_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (monitor.snapshot_id, monitor.monitor_name, monitor.connection_type,
             monitor.resolution, monitor.refresh_rate_hz, monitor.status, monitor.pnp_device_id)
        )
        self.commit()
        return cursor.lastrowid

    def get_monitor_states(self, snapshot_id: int) -> List[Dict[str, Any]]:
        """Get all monitor states for a snapshot"""
        cursor = self.execute(
            "SELECT * FROM monitor_state WHERE snapshot_id = ?",
            (snapshot_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def create_issue(self, issue: Issue) -> int:
        """Create issue record"""
        cursor = self.execute(
            """
            INSERT INTO issues (snapshot_id, issue_type, description, severity)
            VALUES (?, ?, ?, ?)
            """,
            (issue.snapshot_id, issue.issue_type, issue.description, issue.severity)
        )
        self.commit()
        return cursor.lastrowid

    def get_issue(self, issue_id: int) -> Optional[Dict[str, Any]]:
        """Get issue by ID"""
        cursor = self.execute(
            "SELECT * FROM issues WHERE id = ?",
            (issue_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_issues(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get list of issues with pagination"""
        cursor = self.execute(
            """
            SELECT * FROM issues
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset)
        )
        return [dict(row) for row in cursor.fetchall()]

    def create_hardware_state(self, hardware: HardwareState) -> int:
        """Create hardware state record"""
        cursor = self.execute(
            """
            INSERT INTO hardware_state (snapshot_id, component_type, component_data)
            VALUES (?, ?, ?)
            """,
            (hardware.snapshot_id, hardware.component_type, hardware.component_data)
        )
        self.commit()
        return cursor.lastrowid

    def get_hardware_states(self, snapshot_id: int) -> List[Dict[str, Any]]:
        """Get all hardware states for a snapshot"""
        cursor = self.execute(
            "SELECT * FROM hardware_state WHERE snapshot_id = ?",
            (snapshot_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def create_installed_software(self, software: InstalledSoftware) -> int:
        """Create installed software record"""
        cursor = self.execute(
            """
            INSERT INTO installed_software (snapshot_id, software_name, version, install_date)
            VALUES (?, ?, ?, ?)
            """,
            (software.snapshot_id, software.software_name, software.version, software.install_date)
        )
        self.commit()
        return cursor.lastrowid

    def create_system_event(self, event: SystemEvent) -> int:
        """Create system event record"""
        cursor = self.execute(
            """
            INSERT INTO system_events (snapshot_id, event_type, event_source, description, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (event.snapshot_id, event.event_type, event.event_source,
             event.description, event.timestamp)
        )
        self.commit()
        return cursor.lastrowid

    def create_config_change(self, change: ConfigChange) -> int:
        """Create config change record"""
        cursor = self.execute(
            """
            INSERT INTO config_changes (snapshot_id, change_type, component, old_value, new_value)
            VALUES (?, ?, ?, ?, ?)
            """,
            (change.snapshot_id, change.change_type, change.component,
             change.old_value, change.new_value)
        )
        self.commit()
        return cursor.lastrowid

    def get_config_changes(self, snapshot_id: int) -> List[Dict[str, Any]]:
        """Get all config changes for a snapshot"""
        cursor = self.execute(
            "SELECT * FROM config_changes WHERE snapshot_id = ?",
            (snapshot_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


# Global database instance
db = Database()
