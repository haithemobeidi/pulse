"""
PC-Inspector FastAPI Backend

Starts the FastAPI server with all routes configured.
Handles system monitoring data collection, storage, and API queries.

Usage:
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

Access:
    - API: http://localhost:8000
    - Docs: http://localhost:8000/docs
    - OpenAPI: http://localhost:8000/openapi.json
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="PC-Inspector API",
    description="Local-first system monitoring and debugging tool for Windows PCs",
    version="0.1.0"
)

# Add CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost:5173", "127.0.0.1"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Database Initialization
# ============================================================================

from backend.database import db

# Initialize database on startup
try:
    logger.info("Initializing database...")
    db.connect()
    db.create_schema()
    logger.info(f"Database ready: {db.db_path}")
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    sys.exit(1)


# ============================================================================
# Route Registration
# ============================================================================

from backend.api import snapshots, hardware, issues, collect

app.include_router(snapshots.router)
app.include_router(hardware.router)
app.include_router(issues.router)
app.include_router(collect.router)


# ============================================================================
# Health Check Endpoints
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "PC-Inspector",
        "version": "0.1.0"
    }


@app.get("/api/status")
async def api_status():
    """Get API status and system connectivity"""
    from backend.utils.powershell import test_connection

    try:
        if not db.connection:
            db.connect()

        # Test PowerShell connectivity
        ps_ok = test_connection()

        # Get database stats
        snapshot_cursor = db.execute("SELECT COUNT(*) FROM snapshots")
        snapshot_count = snapshot_cursor.fetchone()[0]

        issue_cursor = db.execute("SELECT COUNT(*) FROM issues")
        issue_count = issue_cursor.fetchone()[0]

        return {
            "status": "ok",
            "database": "connected",
            "powershell": "connected" if ps_ok else "disconnected",
            "snapshots": snapshot_count,
            "issues": issue_count
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


# ============================================================================
# Startup/Shutdown Events
# ============================================================================

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    logger.info("Shutting down...")
    db.disconnect()
    logger.info("Database closed")


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
