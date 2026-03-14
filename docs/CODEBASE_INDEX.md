# Pulse (PC-Inspector) - Codebase Index

## Backend Files

| File | Purpose | Status |
|------|---------|--------|
| `backend/app.py` | Flask server - API + static files, all route definitions | Active |
| `backend/database.py` | SQLite schema (13 tables), models, CRUD operations | Active |
| `backend/collectors/base.py` | Base collector class (abstract) | Active |
| `backend/collectors/hardware.py` | GPU (WMI + nvidia-smi), CPU/Memory (psutil) | Active |
| `backend/collectors/monitors.py` | Monitor detection via EDID/WmiMonitorID | Active |
| `backend/collectors/reliability.py` | Windows Reliability Monitor (Win32_ReliabilityRecords) | Active |
| `backend/ai/__init__.py` | AI module init | Active |
| `backend/ai/providers.py` | Multi-provider AI (Ollama/Gemini/Claude) with auto-failover | Active |
| `backend/ai/reasoning.py` | AI reasoning engine - builds context, calls providers, parses diagnosis | Active |
| `backend/ai/learning.py` | Learning engine - pattern detection, fix effectiveness, recommendations | Active |
| `backend/utils/powershell.py` | PowerShell bridge for WSL→Windows queries | Active |

## Frontend Files

| File | Purpose | Status |
|------|---------|--------|
| `frontend/index.html` | HTML entry - Troubleshoot, Dashboard, Issues, Timeline, Hardware pages | Active |
| `frontend/style.css` | Dark theme styling with progress bars, badges | Active |
| `frontend/src/main.js` | Main app logic - navigation, troubleshoot flow, fix approval UI | Active |
| `frontend/src/api/client.ts` | Typed API client (port 5000) | Active |
| `frontend/src/pages/dashboard.ts` | Dashboard page - GPU, monitors, memory, CPU status | Active |
| `frontend/src/pages/issues.ts` | Issues list page | Untested |
| `frontend/src/pages/timeline.ts` | System timeline page | Untested |
| `frontend/src/pages/hardware.ts` | Hardware history page | Untested |

## Configuration Files

| File | Purpose |
|------|---------|
| `requirements.txt` | Python dependencies (flask, psutil, wmi, requests, etc.) |
| `.env` | API keys (GEMINI_API_KEY, ANTHROPIC_API_KEY) - gitignored |
| `.env.example` | Template for .env file |
| `.gitignore` | Git ignore rules |
| `start-pulse.bat` | Windows one-click launcher (opens browser automatically) |
| `Start Pulse.vbs` | Double-click GUI launcher |

## Session Protocols

| File | Purpose |
|------|---------|
| `.claude/commands/start-session.md` | `/start-session` - Initialize dev session |
| `.claude/commands/work-session.md` | `/work-session` - Mid-session check-in |
| `.claude/commands/end-session.md` | `/end-session` - Close session with handoff |

## Documentation

| File | Purpose |
|------|---------|
| `docs/CODEBASE_INDEX.md` | This file - complete file inventory |
| `docs/MASTER_HANDOFF_INDEX.md` | Session handoff history |
| `docs/handoffs/` | Individual session handoff documents |
| `docs/FUTURE_FEATURES.md` | Roadmap for future features |
| `README.md` | Project overview |

## Database

| Location | Purpose |
|----------|---------|
| `data/system.db` | SQLite database (13 tables) |

### Database Tables
| Table | Purpose |
|-------|---------|
| `snapshots` | Point-in-time system state captures |
| `gpu_state` | GPU info per snapshot |
| `monitor_state` | Monitor config per snapshot |
| `issues` | User-reported problems |
| `hardware_state` | CPU/memory data (JSON) |
| `installed_software` | Software inventory |
| `system_events` | Windows Event Log entries |
| `config_changes` | Detected configuration changes |
| `reliability_records` | Windows Reliability Monitor data |
| `ai_analyses` | Stored AI diagnosis results |
| `suggested_fixes` | Fix proposals with approval status |
| `fix_outcomes` | User feedback on fix results |
| `patterns` | Learned correlations and patterns |

## Architecture

```
Browser (http://localhost:5000)
    ↓
Flask Server (backend/app.py)
    ├── Collectors (read-only system queries)
    │   ├── Hardware (WMI + psutil + nvidia-smi)
    │   ├── Monitors (EDID via WmiMonitorID)
    │   └── Reliability (Win32_ReliabilityRecords)
    ├── AI Engine (multi-provider with failover)
    │   ├── Ollama (local, free) → preferred
    │   ├── Gemini (Google subscription) → fallback
    │   └── Claude (pay-per-use) → backup
    ├── Learning Engine
    │   ├── Fix effectiveness tracking
    │   ├── Recurring issue detection
    │   └── Change trigger correlation
    └── Approval System
        └── Pending → Approved → Executed → Outcome
    ↓
SQLite (data/system.db) - 13 tables
```

## Key Technical Details
- **Runtime**: Windows Python 3.12+ via venv (NOT WSL Python)
- **Frontend**: Vanilla JS served by Flask (no build step)
- **Ollama**: Runs on Windows, reachable from WSL at `http://172.21.0.1:11434`
- **EDID Monitor Detection**: Uses `Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorID`
- **GPU Driver Version**: nvidia-smi first, then WMI format conversion (32.0.15.9576 → 595.76)
- **Security**: All scanners read-only, fixes require explicit approval, API keys in .env only

## Last Updated
2026-03-14
