"""
Issues API

Endpoints for logging, retrieving, and managing user-reported issues.
Critical for the PC-Inspector workflow: user logs issue → capture full system snapshot.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from backend.database import db, Issue, Snapshot, SnapshotType, IssueType, IssueSeverity
from backend.collectors.hardware import HardwareCollector
from backend.collectors.monitors import MonitorCollector

router = APIRouter(prefix="/api/issues", tags=["issues"])


# ============================================================================
# Pydantic Models
# ============================================================================

class IssueRequest(BaseModel):
    """Request body for logging an issue"""
    issue_type: str = IssueType.OTHER
    description: str
    severity: str = IssueSeverity.MEDIUM
    snapshot_id: Optional[int] = None


class IssueResponse(BaseModel):
    """Response body for issue data"""
    id: int
    snapshot_id: int
    issue_type: str
    description: str
    severity: str
    timestamp: str

    class Config:
        from_attributes = True


class IssueWithContextResponse(IssueResponse):
    """Issue response with full system context"""
    gpu_state: Optional[dict] = None
    monitors: Optional[List[dict]] = None
    hardware_state: Optional[List[dict]] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.post("", response_model=IssueResponse)
async def log_issue(request: IssueRequest) -> IssueResponse:
    """
    Log a system issue with automatic snapshot capture.

    This is the core workflow:
    1. User experiences a problem (monitor blackout, crash, etc.)
    2. Clicks "Log Issue"
    3. System captures snapshot of current state
    4. Issue is recorded with snapshot reference
    5. Later analysis can correlate issue with system changes

    The snapshot captures:
    - GPU driver version (for driver update correlation)
    - Monitor configuration (for hardware connection issues)
    - CPU, memory, system state
    - All accessible without user configuration

    Args:
        request: IssueRequest with type, description, severity

    Returns:
        IssueResponse with created issue details
    """
    try:
        if not db.connection:
            db.connect()

        # Step 1: Create snapshot if not provided
        if not request.snapshot_id:
            snapshot = Snapshot(
                snapshot_type=SnapshotType.ISSUE_LOGGED,
                notes=f"Issue: {request.issue_type}"
            )
            snapshot_id = db.create_snapshot(snapshot)

            # Step 2: Collect system data for this snapshot
            try:
                hw_collector = HardwareCollector(db)
                hw_collector.collect(snapshot_id)
            except Exception as e:
                # Log error but don't fail issue creation
                print(f"Warning: Hardware collection failed: {e}")

            try:
                monitor_collector = MonitorCollector(db)
                monitor_collector.collect(snapshot_id)
            except Exception as e:
                print(f"Warning: Monitor collection failed: {e}")

        else:
            snapshot_id = request.snapshot_id

        # Step 3: Record the issue
        issue = Issue(
            snapshot_id=snapshot_id,
            issue_type=request.issue_type,
            description=request.description,
            severity=request.severity
        )

        issue_id = db.create_issue(issue)

        return IssueResponse(
            id=issue_id,
            snapshot_id=snapshot_id,
            issue_type=request.issue_type,
            description=request.description,
            severity=request.severity,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to log issue: {str(e)}")


@router.get("/{issue_id}", response_model=IssueWithContextResponse)
async def get_issue(issue_id: int) -> IssueWithContextResponse:
    """
    Get issue with full system context.

    Returns the issue along with the exact system state
    captured when the issue was logged. This allows debugging:
    - "What was the GPU driver version when this crash happened?"
    - "Were all monitors connected when the blackout occurred?"

    Args:
        issue_id: ID of issue to retrieve

    Returns:
        IssueWithContextResponse with issue and system snapshot
    """
    try:
        if not db.connection:
            db.connect()

        issue = db.get_issue(issue_id)
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")

        snapshot_id = issue["snapshot_id"]

        # Get full system context from snapshot
        gpu = db.get_gpu_state(snapshot_id)
        monitors = db.get_monitor_states(snapshot_id)

        hw_cursor = db.execute(
            "SELECT component_type, component_data FROM hardware_state WHERE snapshot_id = ?",
            (snapshot_id,)
        )
        hardware = [dict(row) for row in hw_cursor.fetchall()]

        return IssueWithContextResponse(
            id=issue["id"],
            snapshot_id=issue["snapshot_id"],
            issue_type=issue["issue_type"],
            description=issue["description"],
            severity=issue["severity"],
            timestamp=issue["timestamp"],
            gpu_state=gpu,
            monitors=[dict(m) for m in monitors],
            hardware_state=hardware
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve issue: {str(e)}")


@router.get("", response_model=List[IssueResponse])
async def list_issues(limit: int = 50, offset: int = 0) -> List[IssueResponse]:
    """
    List all logged issues.

    Returns issues in reverse chronological order (newest first).

    Args:
        limit: Maximum number of issues to return (default 50)
        offset: Number of issues to skip (default 0)

    Returns:
        List of IssueResponse objects
    """
    try:
        if not db.connection:
            db.connect()

        issues = db.get_issues(limit=limit, offset=offset)

        return [
            IssueResponse(
                id=i["id"],
                snapshot_id=i["snapshot_id"],
                issue_type=i["issue_type"],
                description=i["description"],
                severity=i["severity"],
                timestamp=i["timestamp"]
            )
            for i in issues
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list issues: {str(e)}")


@router.get("/type/{issue_type}", response_model=List[IssueResponse])
async def get_issues_by_type(issue_type: str, limit: int = 20) -> List[IssueResponse]:
    """
    Get all issues of a specific type.

    Useful for pattern detection:
    - "How many monitor blackouts have occurred?"
    - "When did crashes start happening?"

    Args:
        issue_type: Type of issue to filter by
        limit: Maximum number of results

    Returns:
        List of matching IssueResponse objects
    """
    try:
        if not db.connection:
            db.connect()

        cursor = db.execute(
            """
            SELECT * FROM issues
            WHERE issue_type = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (issue_type, limit)
        )

        return [
            IssueResponse(
                id=row["id"],
                snapshot_id=row["snapshot_id"],
                issue_type=row["issue_type"],
                description=row["description"],
                severity=row["severity"],
                timestamp=row["timestamp"]
            )
            for row in cursor.fetchall()
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query issues: {str(e)}")
