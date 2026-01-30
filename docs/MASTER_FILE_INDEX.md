# PC-Inspector - Master File Index

## Backend Files

| File | Purpose | Status |
|------|---------|--------|
| `backend/app.py` | Flask single-server (API + static files) | ✓ Complete |
| `backend/database.py` | SQLite models and CRUD (check_same_thread=False) | ✓ Complete |
| `backend/collectors/base.py` | Base collector class | ✓ Complete |
| `backend/collectors/hardware.py` | CPU/Memory (psutil), GPU (WMI) collection | ✓ Complete |
| `backend/collectors/monitors.py` | Monitor detection (WMI + registry fallback) | ✓ Complete |
| `backend/utils/powershell.py` | Windows PowerShell utilities (legacy) | ⚠ Deprecated |

## Frontend Files

| File | Purpose | Status |
|------|---------|--------|
| `frontend/index.html` | HTML entry point | ✓ Complete |
| `frontend/style.css` | Styling | ✓ Complete |
| `frontend/src/main.js` | Main application logic | ✓ Complete |
| `frontend/src/api/client.js` | API client | ✓ Complete |
| `frontend/src/pages/dashboard.js` | Dashboard page | ✓ Complete |
| `frontend/src/pages/issues.js` | Issues page | ⚠ Created but not tested |
| `frontend/src/pages/timeline.js` | Timeline page | ⚠ Created but not tested |
| `frontend/src/pages/hardware.js` | Hardware history page | ⚠ Created but not tested |

## Configuration Files

| File | Purpose |
|------|---------|
| `requirements.txt` | Python dependencies |
| `.gitignore` | Git ignore rules |
| `start.bat` | Windows batch startup script |
| `start.ps1` | PowerShell startup script |
| `start.sh` | Bash startup script |

## Documentation

| File | Purpose |
|------|---------|
| `docs/FUTURE_FEATURES.md` | Phase 2+ roadmap: anomaly detection, auto-logging, correlations |
| `README.md` | Project overview |
| `START_HERE.md` | Quick start guide |
| `QUICKSTART.md` | Command-line reference |

## Database

| Location | Purpose | Status |
|----------|---------|--------|
| `data/system.db` | SQLite database | ✓ Created and initialized |
| `scripts/init_database.py` | Database initialization | ✓ Complete |

## Current MVP Status

**Working Features:**
- ✅ Flask server (port 5000) - API + static frontend in one process
- ✅ CPU collection (psutil) - 16 cores, 32 threads, frequency, usage %
- ✅ Memory collection (psutil) - total, available, used, percent
- ✅ GPU detection (WMI) - RTX 5090 detected, driver version captured
- ✅ Monitor detection (WMI + registry) - 2 monitors detected
- ✅ Issue logging with automatic snapshot
- ✅ Dashboard with real-time data display
- ✅ One-click startup (start.bat / start.sh)

**Known Limitations:**
- GPU VRAM showing as "Unknown" (WMI returns invalid values)
- Monitor names generic ("Default Monitor", "Generic PnP Monitor")
- Connection type detection not working (showing "Unknown")

**Architecture Decisions:**
- Switched from PowerShell to Python libraries (psutil, WMI)
- Single Flask server instead of FastAPI + separate frontend
- Plain JavaScript instead of TypeScript (no build step)
- SQLite with check_same_thread=False for thread safety

## Last Updated
2026-01-30 01:20 EST
