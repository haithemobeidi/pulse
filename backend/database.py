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
class ReliabilityRecord:
    """Windows Reliability Monitor record"""
    id: Optional[int] = None
    snapshot_id: int = None
    record_type: str = None  # app_crash, driver_crash, os_crash, app_install, app_uninstall, driver_install, os_update, misc_failure
    source_name: str = None  # Application or component that generated the event
    event_message: str = None
    event_time: Optional[str] = None
    product_name: Optional[str] = None  # Software/driver involved
    stability_index: Optional[float] = None  # Windows stability rating 1-10

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class AiAnalysis:
    """Stored AI analysis result"""
    id: Optional[int] = None
    issue_id: int = None
    diagnosis: Optional[str] = None
    confidence: Optional[float] = None
    root_cause: Optional[str] = None
    raw_response: Optional[str] = None  # Full JSON response
    model_used: Optional[str] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class SuggestedFix:
    """Individual fix suggestion from AI"""
    id: Optional[int] = None
    analysis_id: int = None
    issue_id: int = None
    title: Optional[str] = None
    description: Optional[str] = None
    risk_level: Optional[str] = None
    action_type: Optional[str] = None
    action_detail: Optional[str] = None
    estimated_success: Optional[float] = None
    reversible: bool = True
    status: str = "pending"  # pending, approved, rejected, executed, rolled_back
    approved_at: Optional[str] = None
    executed_at: Optional[str] = None
    execution_output: Optional[str] = None
    execution_success: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class FixOutcome:
    """User-reported outcome of a fix attempt"""
    id: Optional[int] = None
    fix_id: int = None
    issue_id: int = None
    resolved: bool = False
    user_notes: Optional[str] = None
    rated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Pattern:
    """Learned pattern from fix history"""
    id: Optional[int] = None
    pattern_type: Optional[str] = None  # symptom_cluster, hardware_correlation, fix_effectiveness, change_trigger
    description: Optional[str] = None
    evidence: Optional[str] = None  # JSON list of issue_ids
    confidence: float = 0.0
    times_seen: int = 1
    times_failed: int = 0
    last_seen: Optional[str] = None
    last_activity_at: Optional[str] = None
    created_at: Optional[str] = None
    active: bool = True

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


@dataclass
class Embedding:
    """Cached vector embedding for similarity search"""
    id: Optional[int] = None
    entity_type: Optional[str] = None  # 'issue', 'fix', 'pattern'
    entity_id: Optional[int] = None
    embedding: Optional[bytes] = None  # numpy array serialized
    model: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Correction:
    """User correction to AI output — feeds style learning"""
    id: Optional[int] = None
    correction_type: Optional[str] = None  # 'diagnosis_edit', 'fix_edit', 'response_edit'
    original_text: Optional[str] = None
    corrected_text: Optional[str] = None
    context: Optional[str] = None  # JSON: issue_type, hardware_config, etc.
    captured_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class StyleGuide:
    """Generated style guide from user corrections"""
    id: Optional[int] = None
    scope: Optional[str] = None  # 'diagnosis', 'fix_suggestion', 'chat_response'
    guide: Optional[str] = None
    sample_count: int = 0
    correction_count: int = 0
    version: int = 1
    generated_at: Optional[str] = None

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

        -- Reliability Monitor: Windows reliability records (crashes, installs, failures)
        CREATE TABLE IF NOT EXISTS reliability_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            record_type TEXT NOT NULL,
            source_name TEXT,
            event_message TEXT,
            event_time DATETIME,
            product_name TEXT,
            stability_index REAL,
            FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_reliability_snapshot ON reliability_records(snapshot_id);
        CREATE INDEX IF NOT EXISTS idx_reliability_type ON reliability_records(record_type);
        CREATE INDEX IF NOT EXISTS idx_reliability_time ON reliability_records(event_time);

        -- AI Analyses: Stored AI diagnosis results
        CREATE TABLE IF NOT EXISTS ai_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id INTEGER NOT NULL,
            diagnosis TEXT,
            confidence REAL,
            root_cause TEXT,
            raw_response TEXT,
            model_used TEXT,
            tokens_input INTEGER,
            tokens_output INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_ai_analyses_issue ON ai_analyses(issue_id);

        -- Suggested Fixes: Individual fix proposals from AI with approval tracking
        CREATE TABLE IF NOT EXISTS suggested_fixes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id INTEGER NOT NULL,
            issue_id INTEGER NOT NULL,
            title TEXT,
            description TEXT,
            risk_level TEXT,
            action_type TEXT,
            action_detail TEXT,
            estimated_success REAL,
            reversible INTEGER DEFAULT 1,
            status TEXT DEFAULT 'pending',
            approved_at DATETIME,
            executed_at DATETIME,
            execution_output TEXT,
            execution_success INTEGER,
            FOREIGN KEY (analysis_id) REFERENCES ai_analyses(id) ON DELETE CASCADE,
            FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_fixes_analysis ON suggested_fixes(analysis_id);
        CREATE INDEX IF NOT EXISTS idx_fixes_issue ON suggested_fixes(issue_id);
        CREATE INDEX IF NOT EXISTS idx_fixes_status ON suggested_fixes(status);

        -- Fix Outcomes: User feedback on whether fixes worked
        CREATE TABLE IF NOT EXISTS fix_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fix_id INTEGER NOT NULL,
            issue_id INTEGER NOT NULL,
            resolved INTEGER DEFAULT 0,
            user_notes TEXT,
            rated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (fix_id) REFERENCES suggested_fixes(id) ON DELETE CASCADE,
            FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_outcomes_fix ON fix_outcomes(fix_id);
        CREATE INDEX IF NOT EXISTS idx_outcomes_resolved ON fix_outcomes(resolved);

        -- Learned Patterns: Correlations discovered from fix history
        CREATE TABLE IF NOT EXISTS patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT NOT NULL,
            description TEXT NOT NULL,
            evidence TEXT,
            confidence REAL DEFAULT 0.0,
            times_seen INTEGER DEFAULT 1,
            times_failed INTEGER DEFAULT 0,
            last_seen DATETIME,
            last_activity_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            active INTEGER DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type);
        CREATE INDEX IF NOT EXISTS idx_patterns_confidence ON patterns(confidence DESC);

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

        -- Embeddings: Cached vector embeddings for similarity search
        CREATE TABLE IF NOT EXISTS embeddings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            embedding BLOB NOT NULL,
            model TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_embeddings_entity ON embeddings(entity_type, entity_id);

        -- Corrections: User edits to AI output for style learning
        CREATE TABLE IF NOT EXISTS corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            correction_type TEXT NOT NULL,
            original_text TEXT NOT NULL,
            corrected_text TEXT NOT NULL,
            context TEXT,
            captured_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_corrections_type ON corrections(correction_type);

        -- Style Guides: Generated from correction patterns
        CREATE TABLE IF NOT EXISTS style_guides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL,
            guide TEXT NOT NULL,
            sample_count INTEGER DEFAULT 0,
            correction_count INTEGER DEFAULT 0,
            version INTEGER DEFAULT 1,
            generated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_style_guides_scope ON style_guides(scope);

        -- Troubleshooting Facts: The living brain's knowledge base
        CREATE TABLE IF NOT EXISTS troubleshooting_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symptom TEXT NOT NULL,
            diagnosis TEXT,
            resolution TEXT,
            confidence REAL DEFAULT 0.5,
            success_count INTEGER DEFAULT 0,
            failure_count INTEGER DEFAULT 0,
            activation_tier TEXT DEFAULT 'warm',
            last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
            decay_score REAL DEFAULT 1.0,
            hardware_context TEXT,
            source TEXT DEFAULT 'session',
            superseded_by INTEGER REFERENCES troubleshooting_facts(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_facts_symptom ON troubleshooting_facts(symptom);
        CREATE INDEX IF NOT EXISTS idx_facts_activation ON troubleshooting_facts(activation_tier);
        CREATE INDEX IF NOT EXISTS idx_facts_confidence ON troubleshooting_facts(confidence DESC);

        -- Fact Relations: Connections between facts
        CREATE TABLE IF NOT EXISTS fact_relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_fact_id INTEGER NOT NULL,
            target_fact_id INTEGER NOT NULL,
            relation_type TEXT NOT NULL,
            confidence REAL DEFAULT 0.5,
            observation_count INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_fact_id) REFERENCES troubleshooting_facts(id),
            FOREIGN KEY (target_fact_id) REFERENCES troubleshooting_facts(id)
        );
        CREATE INDEX IF NOT EXISTS idx_relations_source ON fact_relations(source_fact_id);
        CREATE INDEX IF NOT EXISTS idx_relations_target ON fact_relations(target_fact_id);

        -- Session Outcomes: Tracks what worked and what didn't (training signal)
        CREATE TABLE IF NOT EXISTS session_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            started_at DATETIME,
            ended_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            symptoms_reported TEXT,
            diagnostics_run TEXT,
            diagnosis_reached TEXT,
            resolution_applied TEXT,
            outcome TEXT,
            user_satisfaction INTEGER,
            ai_provider_used TEXT,
            facts_injected TEXT,
            hardware_hash TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_session_outcomes_session ON session_outcomes(session_id);
        CREATE INDEX IF NOT EXISTS idx_session_outcomes_outcome ON session_outcomes(outcome);

        -- Knowledge Gaps: What the AI can't solve yet
        CREATE TABLE IF NOT EXISTS knowledge_gaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symptom_description TEXT NOT NULL,
            gap_type TEXT NOT NULL,
            frequency INTEGER DEFAULT 1,
            first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved_at DATETIME,
            resolution_fact_id INTEGER REFERENCES troubleshooting_facts(id),
            notes TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_gaps_type ON knowledge_gaps(gap_type);
        CREATE INDEX IF NOT EXISTS idx_gaps_frequency ON knowledge_gaps(frequency DESC);

        -- Session Memory: Per-session key-value store for working memory
        CREATE TABLE IF NOT EXISTS session_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(session_id, key)
        );
        CREATE INDEX IF NOT EXISTS idx_session_memory_session ON session_memory(session_id);
        """

        # Execute schema creation
        self.connection.executescript(schema_sql)
        self.commit()

        # Run migrations for existing databases
        self._run_migrations()

    def _run_migrations(self):
        """Add columns/tables that may be missing from older databases."""
        migrations = [
            ("patterns", "times_failed", "ALTER TABLE patterns ADD COLUMN times_failed INTEGER DEFAULT 0"),
            ("patterns", "last_activity_at", "ALTER TABLE patterns ADD COLUMN last_activity_at DATETIME"),
            ("suggested_fixes", "holding_since", "ALTER TABLE suggested_fixes ADD COLUMN holding_since DATETIME"),
            ("suggested_fixes", "auto_verify_at", "ALTER TABLE suggested_fixes ADD COLUMN auto_verify_at DATETIME"),
        ]
        for table, column, sql in migrations:
            try:
                cursor = self.connection.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in cursor.fetchall()]
                if column not in columns:
                    self.connection.execute(sql)
            except Exception:
                pass

        # Backfill last_activity_at from last_seen where NULL
        try:
            self.connection.execute(
                "UPDATE patterns SET last_activity_at = last_seen WHERE last_activity_at IS NULL AND last_seen IS NOT NULL"
            )
        except Exception:
            pass
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

    def create_reliability_record(self, record: ReliabilityRecord) -> int:
        """Create reliability monitor record"""
        cursor = self.execute(
            """
            INSERT INTO reliability_records
            (snapshot_id, record_type, source_name, event_message, event_time, product_name, stability_index)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (record.snapshot_id, record.record_type, record.source_name,
             record.event_message, record.event_time, record.product_name, record.stability_index)
        )
        self.commit()
        return cursor.lastrowid

    def get_reliability_records(self, snapshot_id: int) -> List[Dict[str, Any]]:
        """Get all reliability records for a snapshot"""
        cursor = self.execute(
            "SELECT * FROM reliability_records WHERE snapshot_id = ? ORDER BY event_time DESC",
            (snapshot_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_recent_reliability_records(self, days: int = 30, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent reliability records across all snapshots"""
        cursor = self.execute(
            """
            SELECT r.*, s.timestamp as snapshot_time
            FROM reliability_records r
            JOIN snapshots s ON r.snapshot_id = s.id
            WHERE r.event_time >= datetime('now', ?)
            ORDER BY r.event_time DESC
            LIMIT ?
            """,
            (f'-{days} days', limit)
        )
        return [dict(row) for row in cursor.fetchall()]

    def create_ai_analysis(self, analysis: AiAnalysis) -> int:
        """Store an AI analysis result"""
        cursor = self.execute(
            """
            INSERT INTO ai_analyses
            (issue_id, diagnosis, confidence, root_cause, raw_response, model_used, tokens_input, tokens_output)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (analysis.issue_id, analysis.diagnosis, analysis.confidence, analysis.root_cause,
             analysis.raw_response, analysis.model_used, analysis.tokens_input, analysis.tokens_output)
        )
        self.commit()
        return cursor.lastrowid

    def get_ai_analyses(self, issue_id: int) -> List[Dict[str, Any]]:
        """Get all AI analyses for an issue"""
        cursor = self.execute(
            "SELECT * FROM ai_analyses WHERE issue_id = ? ORDER BY created_at DESC",
            (issue_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def create_suggested_fix(self, fix: SuggestedFix) -> int:
        """Store a suggested fix"""
        cursor = self.execute(
            """
            INSERT INTO suggested_fixes
            (analysis_id, issue_id, title, description, risk_level, action_type,
             action_detail, estimated_success, reversible, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (fix.analysis_id, fix.issue_id, fix.title, fix.description, fix.risk_level,
             fix.action_type, fix.action_detail, fix.estimated_success,
             1 if fix.reversible else 0, fix.status)
        )
        self.commit()
        return cursor.lastrowid

    def get_suggested_fixes(self, issue_id: int) -> List[Dict[str, Any]]:
        """Get all suggested fixes for an issue"""
        cursor = self.execute(
            "SELECT * FROM suggested_fixes WHERE issue_id = ? ORDER BY estimated_success DESC",
            (issue_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def update_fix_status(self, fix_id: int, status: str, output: str = None, success: bool = None):
        """Update fix status (approve, reject, execute, rollback)"""
        if status == "approved":
            self.execute(
                "UPDATE suggested_fixes SET status = ?, approved_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, fix_id)
            )
        elif status == "executed":
            self.execute(
                """UPDATE suggested_fixes SET status = ?, executed_at = CURRENT_TIMESTAMP,
                   execution_output = ?, execution_success = ? WHERE id = ?""",
                (status, output, 1 if success else 0, fix_id)
            )
        else:
            self.execute(
                "UPDATE suggested_fixes SET status = ? WHERE id = ?",
                (status, fix_id)
            )
        self.commit()

    def get_fix(self, fix_id: int) -> Optional[Dict[str, Any]]:
        """Get a single fix by ID"""
        cursor = self.execute("SELECT * FROM suggested_fixes WHERE id = ?", (fix_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_fix_outcome(self, outcome: FixOutcome) -> int:
        """Record user feedback on whether a fix worked"""
        cursor = self.execute(
            """
            INSERT INTO fix_outcomes (fix_id, issue_id, resolved, user_notes)
            VALUES (?, ?, ?, ?)
            """,
            (outcome.fix_id, outcome.issue_id, 1 if outcome.resolved else 0, outcome.user_notes)
        )
        self.commit()
        return cursor.lastrowid

    def get_fix_outcomes(self, issue_id: int = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get fix outcomes, optionally filtered by issue"""
        if issue_id:
            cursor = self.execute(
                "SELECT * FROM fix_outcomes WHERE issue_id = ? ORDER BY rated_at DESC LIMIT ?",
                (issue_id, limit)
            )
        else:
            cursor = self.execute(
                "SELECT * FROM fix_outcomes ORDER BY rated_at DESC LIMIT ?",
                (limit,)
            )
        return [dict(row) for row in cursor.fetchall()]

    def create_pattern(self, pattern: Pattern) -> int:
        """Store a learned pattern"""
        cursor = self.execute(
            """
            INSERT INTO patterns (pattern_type, description, evidence, confidence, times_seen, times_failed, last_seen, last_activity_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (pattern.pattern_type, pattern.description, pattern.evidence,
             pattern.confidence, pattern.times_seen, pattern.times_failed or 0)
        )
        self.commit()
        return cursor.lastrowid

    def get_active_patterns(self, pattern_type: str = None) -> List[Dict[str, Any]]:
        """Get active learned patterns"""
        if pattern_type:
            cursor = self.execute(
                "SELECT * FROM patterns WHERE active = 1 AND pattern_type = ? ORDER BY confidence DESC",
                (pattern_type,)
            )
        else:
            cursor = self.execute(
                "SELECT * FROM patterns WHERE active = 1 ORDER BY confidence DESC"
            )
        return [dict(row) for row in cursor.fetchall()]

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

    # ========================================================================
    # Embeddings CRUD
    # ========================================================================

    def store_embedding(self, entity_type: str, entity_id: int, embedding_blob: bytes, model: str) -> int:
        """Store or update an embedding for an entity."""
        # Remove existing embedding for this entity
        self.execute(
            "DELETE FROM embeddings WHERE entity_type = ? AND entity_id = ?",
            (entity_type, entity_id)
        )
        cursor = self.execute(
            "INSERT INTO embeddings (entity_type, entity_id, embedding, model) VALUES (?, ?, ?, ?)",
            (entity_type, entity_id, embedding_blob, model)
        )
        self.commit()
        return cursor.lastrowid

    def get_embeddings_by_type(self, entity_type: str) -> List[Dict[str, Any]]:
        """Get all embeddings of a given type."""
        cursor = self.execute(
            "SELECT * FROM embeddings WHERE entity_type = ?",
            (entity_type,)
        )
        return [dict(row) for row in cursor.fetchall()]

    # ========================================================================
    # Corrections CRUD
    # ========================================================================

    def create_correction(self, correction: 'Correction') -> int:
        """Store a user correction."""
        cursor = self.execute(
            "INSERT INTO corrections (correction_type, original_text, corrected_text, context) VALUES (?, ?, ?, ?)",
            (correction.correction_type, correction.original_text, correction.corrected_text, correction.context)
        )
        self.commit()
        return cursor.lastrowid

    def get_corrections(self, correction_type: str = None, since: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get corrections, optionally filtered by type and date."""
        query = "SELECT * FROM corrections WHERE 1=1"
        params = []
        if correction_type:
            query += " AND correction_type = ?"
            params.append(correction_type)
        if since:
            query += " AND captured_at >= ?"
            params.append(since)
        query += " ORDER BY captured_at DESC LIMIT ?"
        params.append(limit)
        cursor = self.execute(query, tuple(params))
        return [dict(row) for row in cursor.fetchall()]

    def count_corrections(self, correction_type: str = None) -> int:
        """Count corrections, optionally by type."""
        if correction_type:
            cursor = self.execute(
                "SELECT COUNT(*) FROM corrections WHERE correction_type = ?",
                (correction_type,)
            )
        else:
            cursor = self.execute("SELECT COUNT(*) FROM corrections")
        return cursor.fetchone()[0]

    # ========================================================================
    # Style Guides CRUD
    # ========================================================================

    def get_style_guide(self, scope: str) -> Optional[Dict[str, Any]]:
        """Get the latest style guide for a scope."""
        cursor = self.execute(
            "SELECT * FROM style_guides WHERE scope = ? ORDER BY version DESC LIMIT 1",
            (scope,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_style_guide(self, guide: 'StyleGuide') -> int:
        """Store a new style guide version."""
        cursor = self.execute(
            "INSERT INTO style_guides (scope, guide, sample_count, correction_count, version) VALUES (?, ?, ?, ?, ?)",
            (guide.scope, guide.guide, guide.sample_count, guide.correction_count, guide.version)
        )
        self.commit()
        return cursor.lastrowid

    # ========================================================================
    # Suggested Fixes — holding state helpers
    # ========================================================================

    def get_fixes_in_holding(self) -> List[Dict[str, Any]]:
        """Get fixes currently in holding state."""
        cursor = self.execute(
            "SELECT * FROM suggested_fixes WHERE status = 'holding'"
        )
        return [dict(row) for row in cursor.fetchall()]

    # ========================================================================
    # Living Brain — Troubleshooting Facts CRUD
    # ========================================================================

    def create_fact(self, symptom: str, diagnosis: str = None, resolution: str = None,
                    confidence: float = 0.5, hardware_context: str = None,
                    source: str = 'session') -> int:
        """Create a new troubleshooting fact."""
        cursor = self.execute(
            """INSERT INTO troubleshooting_facts
               (symptom, diagnosis, resolution, confidence, hardware_context, source)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (symptom, diagnosis, resolution, confidence, hardware_context, source)
        )
        self.commit()
        return cursor.lastrowid

    def get_fact(self, fact_id: int) -> Optional[Dict[str, Any]]:
        """Get a fact by ID and update last_accessed."""
        self.execute(
            "UPDATE troubleshooting_facts SET last_accessed = CURRENT_TIMESTAMP WHERE id = ?",
            (fact_id,)
        )
        self.commit()
        cursor = self.execute("SELECT * FROM troubleshooting_facts WHERE id = ?", (fact_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_facts(self, activation_tier: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get facts, optionally filtered by activation tier."""
        if activation_tier:
            cursor = self.execute(
                "SELECT * FROM troubleshooting_facts WHERE activation_tier = ? ORDER BY confidence DESC LIMIT ?",
                (activation_tier, limit)
            )
        else:
            cursor = self.execute(
                "SELECT * FROM troubleshooting_facts ORDER BY confidence DESC LIMIT ?",
                (limit,)
            )
        return [dict(row) for row in cursor.fetchall()]

    def update_fact_outcome(self, fact_id: int, success: bool):
        """Update a fact's success/failure counts and recalculate confidence."""
        col = 'success_count' if success else 'failure_count'
        self.execute(
            f"""UPDATE troubleshooting_facts
                SET {col} = {col} + 1,
                    confidence = CAST(success_count + (CASE WHEN ? THEN 1 ELSE 0 END) AS REAL) /
                                 (success_count + failure_count + 1),
                    last_accessed = CURRENT_TIMESTAMP,
                    activation_tier = 'hot'
                WHERE id = ?""",
            (success, fact_id)
        )
        self.commit()

    def update_fact_decay(self, fact_id: int, decay_score: float, tier: str):
        """Update a fact's decay score and activation tier (used by nightly cron)."""
        self.execute(
            "UPDATE troubleshooting_facts SET decay_score = ?, activation_tier = ? WHERE id = ?",
            (decay_score, tier, fact_id)
        )
        self.commit()

    def search_facts_keyword(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search facts by keyword matching on symptom, diagnosis, resolution."""
        like = f"%{query}%"
        cursor = self.execute(
            """SELECT *, 1.0 as search_score FROM troubleshooting_facts
               WHERE symptom LIKE ? OR diagnosis LIKE ? OR resolution LIKE ?
               ORDER BY confidence DESC
               LIMIT ?""",
            (like, like, like, limit)
        )
        return [dict(row) for row in cursor.fetchall()]

    def supersede_fact(self, old_fact_id: int, new_fact_id: int):
        """Mark a fact as superseded by a newer one."""
        self.execute(
            "UPDATE troubleshooting_facts SET superseded_by = ? WHERE id = ?",
            (new_fact_id, old_fact_id)
        )
        self.commit()

    # ========================================================================
    # Living Brain — Fact Relations CRUD
    # ========================================================================

    def create_fact_relation(self, source_id: int, target_id: int,
                             relation_type: str, confidence: float = 0.5) -> int:
        """Create a relation between two facts."""
        # Check if relation already exists
        cursor = self.execute(
            """SELECT id, observation_count FROM fact_relations
               WHERE source_fact_id = ? AND target_fact_id = ? AND relation_type = ?""",
            (source_id, target_id, relation_type)
        )
        existing = cursor.fetchone()
        if existing:
            # Increment observation count
            self.execute(
                "UPDATE fact_relations SET observation_count = observation_count + 1, confidence = ? WHERE id = ?",
                (confidence, existing['id'])
            )
            self.commit()
            return existing['id']

        cursor = self.execute(
            """INSERT INTO fact_relations (source_fact_id, target_fact_id, relation_type, confidence)
               VALUES (?, ?, ?, ?)""",
            (source_id, target_id, relation_type, confidence)
        )
        self.commit()
        return cursor.lastrowid

    def get_fact_relations(self, fact_id: int) -> List[Dict[str, Any]]:
        """Get all relations for a fact (both directions)."""
        cursor = self.execute(
            """SELECT fr.*, tf.symptom, tf.diagnosis, tf.resolution, tf.confidence as fact_confidence
               FROM fact_relations fr
               JOIN troubleshooting_facts tf ON (
                   CASE WHEN fr.source_fact_id = ? THEN fr.target_fact_id
                        ELSE fr.source_fact_id END = tf.id
               )
               WHERE fr.source_fact_id = ? OR fr.target_fact_id = ?""",
            (fact_id, fact_id, fact_id)
        )
        return [dict(row) for row in cursor.fetchall()]

    # ========================================================================
    # Living Brain — Session Outcomes CRUD
    # ========================================================================

    def create_session_outcome(self, session_id: str, outcome: str,
                                symptoms: str = None, diagnosis: str = None,
                                resolution: str = None, provider: str = None,
                                facts_injected: str = None, hardware_hash: str = None,
                                satisfaction: int = None) -> int:
        """Record a session outcome."""
        # Get session start time from session_memory
        cursor = self.execute(
            "SELECT MIN(created_at) as started FROM session_memory WHERE session_id = ?",
            (session_id,)
        )
        row = cursor.fetchone()
        started = row['started'] if row else None

        cursor = self.execute(
            """INSERT INTO session_outcomes
               (session_id, started_at, symptoms_reported, diagnosis_reached,
                resolution_applied, outcome, user_satisfaction, ai_provider_used,
                facts_injected, hardware_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, started, symptoms, diagnosis, resolution, outcome,
             satisfaction, provider, facts_injected, hardware_hash)
        )
        self.commit()
        return cursor.lastrowid

    def get_session_outcomes(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent session outcomes."""
        cursor = self.execute(
            "SELECT * FROM session_outcomes ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_outcome_stats(self) -> Dict[str, Any]:
        """Get aggregate outcome statistics."""
        cursor = self.execute(
            """SELECT outcome, COUNT(*) as count
               FROM session_outcomes
               GROUP BY outcome"""
        )
        stats = {row['outcome']: row['count'] for row in cursor.fetchall()}
        total = sum(stats.values())
        stats['total'] = total
        if total > 0:
            stats['resolution_rate'] = stats.get('resolved', 0) / total
        return stats

    # ========================================================================
    # Living Brain — Knowledge Gaps CRUD
    # ========================================================================

    def create_or_update_gap(self, symptom: str, gap_type: str, notes: str = None) -> int:
        """Create a knowledge gap or increment frequency if it exists."""
        # Check for existing similar gap
        cursor = self.execute(
            "SELECT id, frequency FROM knowledge_gaps WHERE symptom_description = ? AND gap_type = ? AND resolved_at IS NULL",
            (symptom, gap_type)
        )
        existing = cursor.fetchone()
        if existing:
            self.execute(
                "UPDATE knowledge_gaps SET frequency = frequency + 1, last_seen = CURRENT_TIMESTAMP WHERE id = ?",
                (existing['id'],)
            )
            self.commit()
            return existing['id']

        cursor = self.execute(
            "INSERT INTO knowledge_gaps (symptom_description, gap_type, notes) VALUES (?, ?, ?)",
            (symptom, gap_type, notes)
        )
        self.commit()
        return cursor.lastrowid

    def resolve_gap(self, gap_id: int, resolution_fact_id: int):
        """Mark a knowledge gap as resolved."""
        self.execute(
            "UPDATE knowledge_gaps SET resolved_at = CURRENT_TIMESTAMP, resolution_fact_id = ? WHERE id = ?",
            (resolution_fact_id, gap_id)
        )
        self.commit()

    def get_open_gaps(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get unresolved knowledge gaps, ordered by frequency."""
        cursor = self.execute(
            "SELECT * FROM knowledge_gaps WHERE resolved_at IS NULL ORDER BY frequency DESC LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]

    # ========================================================================
    # Session Memory CRUD
    # ========================================================================

    def get_session_memory(self, session_id: str) -> Dict[str, str]:
        """Get all memory entries for a session as a dict."""
        cursor = self.execute(
            "SELECT key, value FROM session_memory WHERE session_id = ? ORDER BY updated_at DESC",
            (session_id,)
        )
        return {row['key']: row['value'] for row in cursor.fetchall()}

    def set_session_memory(self, session_id: str, key: str, value: str):
        """Set a session memory entry (insert or update)."""
        self.execute(
            """INSERT INTO session_memory (session_id, key, value, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(session_id, key)
               DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP""",
            (session_id, key, value)
        )
        self.commit()

    def delete_session_memory(self, session_id: str, key: str = None):
        """Delete a specific key or all memory for a session."""
        if key:
            self.execute(
                "DELETE FROM session_memory WHERE session_id = ? AND key = ?",
                (session_id, key)
            )
        else:
            self.execute(
                "DELETE FROM session_memory WHERE session_id = ?",
                (session_id,)
            )
        self.commit()

    def get_all_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get a list of sessions with their memory entry count and last activity."""
        cursor = self.execute(
            """SELECT session_id,
                      COUNT(*) as entry_count,
                      MAX(updated_at) as last_activity,
                      MIN(created_at) as started_at
               FROM session_memory
               GROUP BY session_id
               ORDER BY MAX(updated_at) DESC
               LIMIT ?""",
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]


# Global database instance
db = Database()
