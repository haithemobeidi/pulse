# PC-Inspector: Personal PC Debugging & Personalization Tool

Local-first system monitoring tool for Windows PCs running on WSL2. Captures detailed hardware, driver, and software configuration snapshots to debug issues and track system changes over time.

## Use Case

Monitor blackouts when desk moves? Unexpected crashes? Driver update issues? PC-Inspector logs your system state when problems occur and helps correlate patterns with hardware configuration changes.

## Tech Stack

- **Backend**: Python 3.12 + FastAPI
- **Database**: SQLite (zero-config, local-first)
- **Frontend**: Lightweight TypeScript with vanilla HTML
- **Data Collection**: PowerShell + Python (Windows integration from WSL2)

## Project Status

**Phase 1 (MVP)**: In Development
- [ ] Database schema and initialization
- [ ] PowerShell bridge for Windows queries
- [ ] Data collectors (GPU, monitors, drivers)
- [ ] FastAPI backend with core endpoints
- [ ] Simple frontend interface
- [ ] Issue logging with automatic snapshots
- [ ] Timeline view

## Quick Start (WIP)

```bash
# Setup
cd pc-inspector
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Initialize database
python scripts/init_database.py

# Run backend
python backend/main.py

# Run frontend (separate terminal)
cd frontend
python -m http.server 8080

# Access
- Frontend: http://localhost:8080
- API Docs: http://localhost:8000/docs
```

## Architecture

```
Frontend (TypeScript)
    ↓
FastAPI Backend (Python)
    ↓
PowerShell Bridge (Windows integration)
    ↓
SQLite Database (local storage)
```

## Database Tables

- **snapshots**: System state captures (timestamp, type, notes)
- **gpu_state**: GPU info (driver version, VRAM, temp)
- **monitor_state**: Monitor configuration (connection type, resolution)
- **issues**: User-logged problems (type, description, severity)
- **hardware_state**: CPU, RAM, motherboard tracking
- **installed_software**: Software inventory
- **system_events**: Windows Event Log integration
- **config_changes**: Driver/software update tracking

## Development

- Follow coordination patterns: `/home/haith/documents/CLAUDE_AGENT_COORDINATION.md`
- One feature at a time, complete and tested before next
- User confirmation required before marking features complete
- Commit after user confirms functionality works

## Next Steps

1. Initialize Python virtual environment and dependencies
2. Create SQLite database schema
3. Build PowerShell integration bridge
4. Implement data collectors
5. Create FastAPI endpoints
6. Build simple frontend
7. Test issue logging end-to-end
