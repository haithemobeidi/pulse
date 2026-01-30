"""
Hardware API

Endpoints for retrieving current hardware status and historical data.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional, Dict, Any, List
from backend.database import db
from backend.collectors.hardware import HardwareCollector
from backend.collectors.monitors import MonitorCollector
from backend.database import Snapshot, SnapshotType

router = APIRouter(prefix="/api/hardware", tags=["hardware"])


@router.get("/current", response_model=Dict[str, Any])
async def get_current_hardware() -> Dict[str, Any]:
    """
    Get current system hardware status.

    Includes:
    - GPU information (name, driver version, VRAM)
    - Monitor configuration (count, types, connection)
    - CPU and memory
    - All collected from most recent snapshot

    Returns:
        Dictionary with current hardware state
    """
    try:
        if not db.connection:
            db.connect()

        # Get the most recent snapshot
        cursor = db.execute(
            "SELECT id FROM snapshots ORDER BY timestamp DESC LIMIT 1"
        )
        row = cursor.fetchone()

        if not row:
            return {"status": "no_data", "message": "No snapshots available"}

        latest_snapshot_id = row[0]

        # Get GPU info
        gpu = db.get_gpu_state(latest_snapshot_id)
        monitors = db.get_monitor_states(latest_snapshot_id)

        # Get hardware state (CPU, memory)
        hardware_cursor = db.execute(
            "SELECT component_type, component_data FROM hardware_state WHERE snapshot_id = ?",
            (latest_snapshot_id,)
        )
        hardware_states = {}
        for row in hardware_cursor.fetchall():
            hardware_states[row[0]] = row[1]

        return {
            "status": "ok",
            "snapshot_id": latest_snapshot_id,
            "gpu": gpu,
            "monitors": [dict(m) for m in monitors] if monitors else [],
            "monitor_count": len(monitors) if monitors else 0,
            "cpu": hardware_states.get("cpu"),
            "memory": hardware_states.get("memory")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get hardware status: {str(e)}")


@router.get("/gpu", response_model=Optional[Dict[str, Any]])
async def get_gpu_status() -> Optional[Dict[str, Any]]:
    """
    Get current GPU status from most recent snapshot.

    Returns GPU information:
    - Model name
    - Driver version (critical for driver update correlation)
    - VRAM total and used
    - Temperature
    - Clock speed

    Returns:
        GPU state dictionary or null if no data
    """
    try:
        if not db.connection:
            db.connect()

        cursor = db.execute(
            "SELECT id FROM snapshots ORDER BY timestamp DESC LIMIT 1"
        )
        row = cursor.fetchone()

        if not row:
            return None

        gpu = db.get_gpu_state(row[0])
        return gpu

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get GPU status: {str(e)}")


@router.get("/gpu/history", response_model=List[Dict[str, Any]])
async def get_gpu_history(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get GPU status history across snapshots.

    Useful for tracking:
    - Driver version changes
    - Temperature trends
    - Correlating crashes/blackouts with GPU changes

    Args:
        limit: Number of historical entries to return

    Returns:
        List of GPU states from recent snapshots
    """
    try:
        if not db.connection:
            db.connect()

        cursor = db.execute(
            """
            SELECT g.* FROM gpu_state g
            INNER JOIN snapshots s ON g.snapshot_id = s.id
            ORDER BY s.timestamp DESC
            LIMIT ?
            """,
            (limit,)
        )

        return [dict(row) for row in cursor.fetchall()]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get GPU history: {str(e)}")


@router.get("/monitors", response_model=List[Dict[str, Any]])
async def get_monitor_status() -> List[Dict[str, Any]]:
    """
    Get current monitor configuration from most recent snapshot.

    Returns all connected monitors with:
    - Monitor name/model
    - Connection type (DisplayPort, HDMI, etc.) ⭐ Critical for user's use case
    - Status (connected/disconnected)
    - Resolution and refresh rate (if available)

    Returns:
        List of monitor states
    """
    try:
        if not db.connection:
            db.connect()

        cursor = db.execute(
            "SELECT id FROM snapshots ORDER BY timestamp DESC LIMIT 1"
        )
        row = cursor.fetchone()

        if not row:
            return []

        monitors = db.get_monitor_states(row[0])
        return [dict(m) for m in monitors]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get monitor status: {str(e)}")


@router.get("/monitors/history", response_model=List[Dict[str, Any]])
async def get_monitor_history(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get monitor configuration history.

    Useful for detecting:
    - Connection type changes
    - Monitor disconnections (correlate with blackouts)
    - Hardware changes

    Args:
        limit: Number of historical snapshots to include

    Returns:
        List of monitor states from recent snapshots
    """
    try:
        if not db.connection:
            db.connect()

        cursor = db.execute(
            """
            SELECT m.*, s.timestamp FROM monitor_state m
            INNER JOIN snapshots s ON m.snapshot_id = s.id
            ORDER BY s.timestamp DESC, m.id DESC
            LIMIT ?
            """,
            (limit * 3,)  # More entries since multiple monitors per snapshot
        )

        return [dict(row) for row in cursor.fetchall()]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get monitor history: {str(e)}")
