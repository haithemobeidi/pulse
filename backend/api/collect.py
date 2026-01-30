"""
Data Collection API

Endpoints to trigger manual data collection and get collection status.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from backend.database import db, Snapshot, SnapshotType
from backend.collectors.hardware import HardwareCollector
from backend.collectors.monitors import MonitorCollector

router = APIRouter(prefix="/api/collect", tags=["collection"])


@router.post("/all", response_model=Dict[str, Any])
async def collect_all() -> Dict[str, Any]:
    """
    Trigger full system data collection.

    Collects:
    - GPU information and driver version
    - Monitor configuration and connection types
    - CPU and memory information
    - Creates snapshot with all data

    This endpoint is called:
    1. When user logs an issue (automatic)
    2. Manually by user to capture current state
    3. On a schedule (in background task - to be implemented)

    Returns:
        Dictionary with collection status and snapshot ID
    """
    try:
        if not db.connection:
            db.connect()

        # Create snapshot
        snapshot = Snapshot(
            snapshot_type=SnapshotType.SCHEDULED,
            notes="Manual data collection"
        )
        snapshot_id = db.create_snapshot(snapshot)

        results = {
            "status": "success",
            "snapshot_id": snapshot_id,
            "collections": {}
        }

        # Collect hardware data
        try:
            hw_collector = HardwareCollector(db)
            if hw_collector.collect(snapshot_id):
                results["collections"]["hardware"] = "ok"
            else:
                results["collections"]["hardware"] = "no_data"
        except Exception as e:
            results["collections"]["hardware"] = f"error: {str(e)}"

        # Collect monitor data
        try:
            monitor_collector = MonitorCollector(db)
            if monitor_collector.collect(snapshot_id):
                results["collections"]["monitors"] = "ok"
            else:
                results["collections"]["monitors"] = "no_data"
        except Exception as e:
            results["collections"]["monitors"] = f"error: {str(e)}"

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Data collection failed: {str(e)}"
        )


@router.post("/hardware", response_model=Dict[str, Any])
async def collect_hardware() -> Dict[str, Any]:
    """
    Trigger hardware-only data collection.

    Collects GPU, CPU, memory without monitor data.

    Returns:
        Dictionary with collection status
    """
    try:
        if not db.connection:
            db.connect()

        # Create snapshot
        snapshot = Snapshot(
            snapshot_type=SnapshotType.SCHEDULED,
            notes="Hardware collection"
        )
        snapshot_id = db.create_snapshot(snapshot)

        hw_collector = HardwareCollector(db)
        success = hw_collector.collect(snapshot_id)

        return {
            "status": "success" if success else "no_data",
            "snapshot_id": snapshot_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hardware collection failed: {str(e)}")


@router.post("/monitors", response_model=Dict[str, Any])
async def collect_monitors() -> Dict[str, Any]:
    """
    Trigger monitor-only data collection.

    ⭐ Useful for user's monitor blackout debugging.
    Can run frequently to detect connection state changes.

    Returns:
        Dictionary with collection status and snapshot ID
    """
    try:
        if not db.connection:
            db.connect()

        # Create snapshot
        snapshot = Snapshot(
            snapshot_type=SnapshotType.SCHEDULED,
            notes="Monitor collection"
        )
        snapshot_id = db.create_snapshot(snapshot)

        monitor_collector = MonitorCollector(db)
        success = monitor_collector.collect(snapshot_id)

        return {
            "status": "success" if success else "no_data",
            "snapshot_id": snapshot_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Monitor collection failed: {str(e)}")
