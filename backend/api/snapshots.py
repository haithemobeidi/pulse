"""
Snapshots API

Endpoints for creating, retrieving, and managing system snapshots.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from backend.database import Snapshot, SnapshotType, db

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])


# ============================================================================
# Pydantic Models for Request/Response Validation
# ============================================================================

class CreateSnapshotRequest(BaseModel):
    """Request body for creating a snapshot"""
    snapshot_type: str = SnapshotType.MANUAL
    notes: Optional[str] = None


class SnapshotResponse(BaseModel):
    """Response body for snapshot data"""
    id: int
    timestamp: str
    snapshot_type: str
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class SnapshotDetailResponse(SnapshotResponse):
    """Detailed snapshot response with associated data"""
    gpu_info: Optional[dict] = None
    monitors: Optional[List[dict]] = None
    issues_count: int = 0


# ============================================================================
# Endpoints
# ============================================================================

@router.post("", response_model=SnapshotResponse)
async def create_snapshot(request: CreateSnapshotRequest) -> SnapshotResponse:
    """
    Create a new system snapshot.

    Snapshots capture the current system state (GPU, monitors, etc.)
    at a point in time. They can be triggered manually, scheduled,
    or automatically when issues are logged.

    Args:
        request: CreateSnapshotRequest with snapshot_type and optional notes

    Returns:
        SnapshotResponse with created snapshot details
    """
    try:
        if not db.connection:
            db.connect()

        snapshot = Snapshot(
            snapshot_type=request.snapshot_type,
            notes=request.notes
        )

        snapshot_id = db.create_snapshot(snapshot)

        # Return created snapshot
        return SnapshotResponse(
            id=snapshot_id,
            timestamp=datetime.now().isoformat(),
            snapshot_type=request.snapshot_type,
            notes=request.notes
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create snapshot: {str(e)}")


@router.get("/{snapshot_id}", response_model=SnapshotDetailResponse)
async def get_snapshot(snapshot_id: int) -> SnapshotDetailResponse:
    """
    Get detailed snapshot information.

    Returns snapshot with associated data:
    - GPU information
    - Monitor configuration
    - Related issues
    - Hardware state

    Args:
        snapshot_id: ID of snapshot to retrieve

    Returns:
        SnapshotDetailResponse with full snapshot details
    """
    try:
        if not db.connection:
            db.connect()

        snapshot = db.get_snapshot(snapshot_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")

        # Get associated data
        gpu = db.get_gpu_state(snapshot_id)
        monitors = db.get_monitor_states(snapshot_id)

        # Count related issues
        cursor = db.execute(
            "SELECT COUNT(*) FROM issues WHERE snapshot_id = ?",
            (snapshot_id,)
        )
        issues_count = cursor.fetchone()[0]

        return SnapshotDetailResponse(
            id=snapshot["id"],
            timestamp=snapshot["timestamp"],
            snapshot_type=snapshot["snapshot_type"],
            notes=snapshot["notes"],
            gpu_info=gpu,
            monitors=[dict(m) for m in monitors],
            issues_count=issues_count
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve snapshot: {str(e)}")


@router.get("", response_model=List[SnapshotResponse])
async def list_snapshots(limit: int = 50, offset: int = 0) -> List[SnapshotResponse]:
    """
    List all snapshots with pagination.

    Returns snapshots in reverse chronological order (newest first).

    Args:
        limit: Maximum number of snapshots to return (default 50)
        offset: Number of snapshots to skip (default 0)

    Returns:
        List of SnapshotResponse objects
    """
    try:
        if not db.connection:
            db.connect()

        snapshots = db.get_snapshots(limit=limit, offset=offset)

        return [
            SnapshotResponse(
                id=s["id"],
                timestamp=s["timestamp"],
                snapshot_type=s["snapshot_type"],
                notes=s["notes"]
            )
            for s in snapshots
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list snapshots: {str(e)}")
