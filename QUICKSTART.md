# PC-Inspector Quick Start

## Setup

### 1. Create Python Virtual Environment

```bash
cd pc-inspector
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Initialize Database

```bash
python scripts/init_database.py
```

This creates `data/system.db` with all required tables.

## Running

### Terminal 1: Start Backend

```bash
source venv/bin/activate
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The backend will start on `http://localhost:8000`

- API endpoints: `http://localhost:8000/api/*`
- API documentation: `http://localhost:8000/docs` (Swagger UI)
- OpenAPI spec: `http://localhost:8000/openapi.json`

### Terminal 2: Serve Frontend

```bash
cd frontend
python -m http.server 8080
```

The frontend will be available at `http://localhost:8080`

## Testing the API

### Test PowerShell Bridge & Data Collection

```bash
# Trigger full data collection
curl -X POST http://localhost:8000/api/collect/all

# Get current hardware status
curl http://localhost:8000/api/hardware/current

# List snapshots
curl http://localhost:8000/api/snapshots
```

### Test Issue Logging

```bash
# Log an issue
curl -X POST http://localhost:8000/api/issues \
  -H "Content-Type: application/json" \
  -d '{
    "issue_type": "monitor_blackout",
    "description": "Monitor went black when I moved my desk",
    "severity": "high"
  }'

# Get all issues
curl http://localhost:8000/api/issues
```

### Test Using Swagger UI

1. Open `http://localhost:8000/docs`
2. Try out any endpoint directly from the browser interface

## Workflow: Logging a Monitor Blackout Issue

1. Open `http://localhost:8080` in browser
2. Click **"Log Issue"** button
3. Select issue type: **"Monitor Blackout"**
4. Set severity: **"High"**
5. Enter description: *"Monitor went black when I moved desk, connected via DisplayPort"*
6. Click **"Log Issue"**

System will:
- Create a snapshot of current system state
- Collect GPU info (driver version, VRAM, temp)
- Collect monitor configuration (connection types, status)
- Store issue with full snapshot reference
- Show success notification

You can then view:
- **Dashboard**: See GPU and monitor status when issue occurred
- **Issues**: Browse all logged issues
- **Timeline**: See chronological view of issues and snapshots
- **Hardware**: View GPU driver history and monitor connection changes

## Database

SQLite database is stored at: `data/system.db`

Tables:
- `snapshots` - System captures
- `gpu_state` - GPU data per snapshot
- `monitor_state` - Monitor config per snapshot
- `issues` - User-logged issues
- `hardware_state` - CPU, memory, motherboard info
- `system_events` - Windows Event Log entries
- `config_changes` - Detected changes over time
- `installed_software` - Software inventory

## Architecture

```
Frontend (localhost:8080)
    ↓ fetch API calls
Backend (localhost:8000)
    ↓ PowerShell queries
Windows (via WSL2)
    ↓ queries
SQLite Database (data/system.db)
```

## Data Collection

When you log an issue or click "Collect Data":

1. Backend creates a snapshot record
2. Collectors run in parallel:
   - **HardwareCollector**: GPU, CPU, RAM info via PowerShell
   - **MonitorCollector**: Monitor status via PnP queries
3. Data stored in database with snapshot reference
4. Frontend queries and displays results

## Troubleshooting

### Backend won't start

```
ModuleNotFoundError: No module named 'fastapi'
```

Make sure virtual environment is activated and pip install completed:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### PowerShell queries fail

The PowerShell bridge requires WSL2 with access to Windows PowerShell.

Check connectivity:
```bash
python -c "from backend.utils.powershell import test_connection; print('OK' if test_connection() else 'FAILED')"
```

### Frontend can't reach backend

Make sure:
1. Backend is running on `http://localhost:8000`
2. CORS is enabled (default in code)
3. No firewall blocking localhost connections

## Next Steps

1. **Testing**: Log some issues, verify snapshot data is captured
2. **Patterns**: After multiple issues, check if timeline shows correlations
3. **Customization**: Modify issue types, add new data collectors
4. **Scheduling**: Set up background task for periodic data collection
5. **Analysis**: Implement correlation engine to detect patterns

## Architecture for Future

- [ ] Background scheduler for periodic snapshots every 4 hours
- [ ] Windows Event Log integration (display errors, driver crashes)
- [ ] Driver update detection (auto-detect driver changes)
- [ ] Pattern correlation engine
- [ ] Recommendation system
- [ ] Real-time metrics via WebSocket
- [ ] Export/backup functionality
