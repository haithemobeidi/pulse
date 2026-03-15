# Pulse (PC-Inspector) - Codebase Index

## Backend Files

| File | Purpose | Status |
|------|---------|--------|
| `backend/app.py` | Flask server - blueprint registration, SSE endpoint, static serving, startup collection, scheduler | Active |
| `backend/database.py` | SQLite schema (16 tables), models, CRUD operations, migrations | Active |
| `backend/collectors/base.py` | Base collector class (abstract) | Active |
| `backend/collectors/hardware.py` | GPU, CPU, Memory, Motherboard, Storage, Network collectors (WMI + psutil) | Active |
| `backend/collectors/monitors.py` | Monitor detection via EDID/WmiMonitorID | Active |
| `backend/collectors/reliability.py` | Windows Reliability Monitor (Win32_ReliabilityRecords) | Active |
| `backend/ai/__init__.py` | AI module init | Active |
| `backend/ai/providers.py` | Multi-provider AI (Ollama/Gemini/Claude) with auto-failover + conversation history support | Active |
| `backend/ai/reasoning.py` | AI reasoning engine - adaptive context, similar fixes injection, style guide injection | Active |
| `backend/ai/learning.py` | Learning engine - confidence decay, pattern detection, fix effectiveness, recommendations | Active |
| `backend/utils/powershell.py` | PowerShell bridge for WSL→Windows queries | Active |

### Routes (Blueprint modules)
| File | Purpose | Status |
|------|---------|--------|
| `backend/routes/__init__.py` | Blueprint init, server start timestamp | Active |
| `backend/routes/ai.py` | AI analysis and chat endpoints | Active |
| `backend/routes/collection.py` | Data collection trigger endpoint | Active |
| `backend/routes/corrections.py` | User correction capture and stats | Active |
| `backend/routes/fixes.py` | Fix approval, execution, outcome recording | Active |
| `backend/routes/hardware.py` | Hardware state and history endpoints | Active |
| `backend/routes/issues.py` | Issue CRUD endpoints | Active |
| `backend/routes/reliability.py` | Reliability record endpoints | Active |
| `backend/routes/snapshots.py` | Snapshot CRUD endpoints | Active |
| `backend/routes/system.py` | Health, status, live-stats, patterns, recommendations, learning API | Active |

### Services
| File | Purpose | Status |
|------|---------|--------|
| `backend/services/analysis.py` | Full analysis flow: collect → AI → store → embed | Active |
| `backend/services/chat.py` | Conversational follow-up with adaptive context | Active |
| `backend/services/collection.py` | Parallel data collection with SSE progress events | Active |
| `backend/services/context.py` | Adaptive context builder - keyword relevance scoring, token budgeting | Active |
| `backend/services/embeddings.py` | Vector embeddings (Ollama/Gemini/TF-IDF fallback) for similarity search | Active |
| `backend/services/events.py` | SSE event broadcasting to connected clients | Active |
| `backend/services/fixes.py` | Fix lifecycle with state machine, holding period, confidence adjustments | Active |
| `backend/services/matching.py` | Similarity matching - finds relevant past fixes via embeddings | Active |
| `backend/services/scheduler.py` | Background scheduler - auto-resolves fixes past holding period | Active |
| `backend/services/screenshots.py` | Screenshot saving and description | Active |
| `backend/services/state_machine.py` | Fix state machine: pending→approved→executed→holding→resolved/failed | Active |
| `backend/services/style_learning.py` | Style guide generation from user corrections | Active |

## Frontend Files

| File | Purpose | Status |
|------|---------|--------|
| `frontend/index.html` | HTML entry - Troubleshoot, Dashboard, Issues, Timeline, Learning (5 pages) | Active |
| `frontend/style.css` | Dark theme styling - all pages, learning dashboard, timeline filters | Active |
| `frontend/src/main.js` | App init, navigation, notifications, page routing | Active |
| `frontend/src/api/client.js` | API client (port 5000) - endpoint wrappers | Active |
| `frontend/src/api/events.js` | SSE client - auto-reconnect with exponential backoff | Active |
| `frontend/src/pages/dashboard.js` | Dashboard - 7 hw cards, health summary, live stats polling | Active |
| `frontend/src/pages/issues.js` | Issues list page | Active |
| `frontend/src/pages/timeline.js` | Timeline - color-coded, filterable (system/crash/user/AI categories) | Active |
| `frontend/src/pages/troubleshoot.js` | Chat UI, screenshot handling, fix approval, correction editing, SSE progress | Active |
| `frontend/src/pages/learning.js` | Learning dashboard - patterns, fixes, corrections, style guides | Active |
| `frontend/src/components/data-collection.js` | Collect Data button with per-collector SSE progress | Active |
| `frontend/src/components/heartbeat.js` | Server heartbeat / auto-reload detection | Active |
| `frontend/src/components/issue-modal.js` | Issue logging modal | Active |
| `frontend/src/utils.js` | Shared utilities - escapeHtml, formatType, API_BASE | Active |

## Launcher / Manager Files

| File | Purpose |
|------|---------|
| `pulse_manager.pyw` | Python/tkinter GUI - Start/Stop/Restart server with live log output |
| `Pulse Manager.vbs` | Double-click launcher for pulse_manager.pyw (no console flash) |
| `pulse-manager.bat` | CLI-based server manager (menu-driven) |
| `start-pulse.bat` | Simple start script (opens browser automatically) |
| `Start Pulse.vbs` | Double-click launcher for start-pulse.bat |

## Configuration Files

| File | Purpose |
|------|---------|
| `requirements.txt` | Python dependencies (flask, psutil, wmi, requests, pynvml, etc.) |
| `.env` | API keys (GEMINI_API_KEY, ANTHROPIC_API_KEY) - gitignored |
| `.env.example` | Template for .env file |
| `.gitignore` | Git ignore rules |

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
| `data/system.db` | SQLite database (16 tables) |

### Database Tables
| Table | Purpose |
|-------|---------|
| `snapshots` | Point-in-time system state captures |
| `gpu_state` | GPU info per snapshot |
| `monitor_state` | Monitor config per snapshot |
| `issues` | User-reported problems |
| `hardware_state` | CPU/memory/motherboard/storage/network data (JSON) |
| `installed_software` | Software inventory |
| `system_events` | Windows Event Log entries |
| `config_changes` | Detected configuration changes |
| `reliability_records` | Windows Reliability Monitor data |
| `ai_analyses` | Stored AI diagnosis results |
| `suggested_fixes` | Fix proposals with approval/holding/state tracking |
| `fix_outcomes` | User feedback on fix results |
| `patterns` | Learned correlations with confidence decay |
| `embeddings` | Vector embeddings for similarity search |
| `corrections` | User edits to AI output for style learning |
| `style_guides` | Generated style guides from correction patterns |

## Architecture

```
Browser (http://localhost:5000)
    |
Flask Server (backend/app.py) — threaded
    |-- Routes (blueprints)
    |   |-- /api/ai/* — analysis, chat
    |   |-- /api/fixes/* — approve, execute, outcome
    |   |-- /api/corrections — capture user edits
    |   |-- /api/learning/* — patterns, fixes, embeddings
    |   |-- /api/events — SSE stream
    |   +-- /api/hardware, issues, snapshots, reliability, collection, system
    |-- Services
    |   |-- analysis — collect + AI + store + embed
    |   |-- context — adaptive context builder (keyword relevance)
    |   |-- embeddings — vector embeddings (Ollama/Gemini/TF-IDF)
    |   |-- matching — similarity search for past fixes
    |   |-- fixes — state machine lifecycle
    |   |-- scheduler — background holding period checks
    |   |-- events — SSE broadcasting
    |   +-- style_learning — correction → style guide generation
    |-- Collectors (read-only, parallel execution)
    |   |-- Hardware (GPU, CPU, Memory, Motherboard, Storage, Network)
    |   |-- Monitors (EDID via WmiMonitorID)
    |   +-- Reliability (Win32_ReliabilityRecords)
    |-- AI Engine (multi-provider with failover)
    |   |-- Ollama (local, free) -> preferred
    |   |-- Gemini (Google subscription) -> fallback
    |   +-- Claude (pay-per-use) -> backup
    +-- Learning Engine (H3-inspired)
        |-- Confidence decay (30-day half-life)
        |-- Fix similarity matching (cosine similarity + confidence)
        |-- State machine (pending→approved→executed→holding→resolved)
        +-- Correction learning (3+ edits → style guide)
    |
SQLite (data/system.db) - 16 tables
```

## Key Technical Details
- **Runtime**: Windows Python 3.12+ via venv (NOT WSL Python)
- **Frontend**: Vanilla JS modules served by Flask (no build step)
- **Ollama**: Runs on Windows, reachable from WSL at `http://172.21.0.1:11434`
- **EDID Monitor Detection**: Uses `Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorID`
- **GPU Driver Version**: nvidia-smi first, then WMI format conversion (32.0.15.9576 -> 595.76)
- **Parallel Collection**: All collectors run in ThreadPoolExecutor (3 workers, 45s timeout)
- **Security**: All scanners read-only, fixes require explicit approval, API keys in .env only
- **SSE**: Real-time progress events via `/api/events` with exponential backoff reconnect
- **Confidence Decay**: `effective = stored * 0.5^(days/30)` — patterns fade if not reinforced
- **Similarity Scoring**: `score = cosine_similarity * 0.7 + decayed_confidence * 0.3`
- **User Hardware**: RTX 5090 (32GB), Ryzen 9 9950X3D, 96GB DDR5-6000 Corsair, AM5, AW3425DW + LG ULTRAGEAR

## Last Updated
2026-03-15
