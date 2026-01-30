# PC-Inspector: START HERE

Welcome! This is a complete system monitoring tool for debugging your PC issues. Follow these steps to get it running.

## What This Does

PC-Inspector monitors your PC hardware (GPU, monitors, CPU, RAM) and logs issues with full system context. Perfect for debugging your monitor blackout problem - it captures exactly what your system state was when the blackout occurred.

## Prerequisites

- Windows 10/11 with WSL2 (Linux subsystem)
- Python 3.12 installed
- A browser (Chrome, Firefox, Edge, etc.)

## Installation (First Time Only)

### Step 1: Open WSL2 Terminal

In Windows, open PowerShell or Windows Terminal and run:
```powershell
wsl
```

This opens the Linux subsystem. All commands below run in this terminal.

### Step 2: Navigate to Project

```bash
cd /mnt/c/Users/haith/Documents/Vibe\ Projects/pc-inspector
```

### Step 3: Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` at the start of your terminal prompt.

### Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

Wait for this to complete (1-2 minutes).

### Step 5: Initialize Database

```bash
python scripts/init_database.py
```

You should see:
```
✓ Database initialized successfully!
```

## Running PC-Inspector

### Terminal 1: Start Backend (Keep Running)

In WSL2, from the pc-inspector directory:

```bash
source venv/bin/activate
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

You should see something like:
```
Uvicorn running on http://0.0.0.0:8000
```

**Keep this terminal open while using PC-Inspector.**

### Terminal 2: Start Frontend (Keep Running)

Open a **second** terminal (new PowerShell or Terminal tab):

```bash
wsl
cd /mnt/c/Users/haith/Documents/Vibe\ Projects/pc-inspector/frontend
python -m http.server 8080
```

You should see:
```
Serving HTTP on 0.0.0.0 port 8080
```

**Keep this terminal open while using PC-Inspector.**

### Terminal 3: Open Dashboard

Open a **browser** tab and navigate to:

```
http://localhost:8080
```

You should see the PC-Inspector dashboard with:
- Current GPU status (NVIDIA RTX 5090 info)
- Your 4 monitors listed
- Memory and CPU information
- Recent issues section (empty at first)

## Your First Use

### Step 1: Collect Baseline Data

On the dashboard:
1. Click the **"Collect Data"** button
2. Wait 1-2 seconds for collection
3. Dashboard should refresh showing your hardware

You should see:
- GPU: NVIDIA RTX 5090 (or your GPU)
- Driver: 591.74 (or your driver version)
- Monitors: Your 4 monitors with connection types
- Memory: Total, used, free amounts

This is your baseline state.

### Step 2: When a Monitor Blackout Occurs

**While it's happening or immediately after:**

1. Open browser to `http://localhost:8080`
2. Click **"Log Issue"** button
3. A form will appear:
   ```
   Issue Type: Monitor Blackout (select from dropdown)
   Severity: High (select from dropdown)
   Description: "Monitor went black when I moved my desk,
                lasted about 2 seconds, then came back.
                All monitors affected / just monitor 2?"
   ```
4. Click **"Log Issue"** button

The system will:
- Create a snapshot of your exact system state
- Capture GPU driver version
- Record which monitors are connected
- Store everything with timestamp

### Step 3: Analyze Patterns

After logging 5-10 incidents:

1. Click **"Timeline"** tab
   - See all your blackout incidents chronologically
   - See when they happened
   - Look for patterns (time of day, frequency, etc.)

2. Click **"Hardware"** tab
   - See GPU driver version history
   - See monitor connection changes
   - Look for driver updates before blackouts

3. Click **"Issues"** tab
   - See all your logged blackouts
   - Each one shows the full system state from when it happened

## Troubleshooting

### "Connection refused" error

**Problem:** Can't open `http://localhost:8080`

**Solution:**
1. Make sure both Terminal 1 and Terminal 2 are still running
2. Check that Terminal 1 shows "Uvicorn running on..."
3. Check that Terminal 2 shows "Serving HTTP on..."
4. Try `http://127.0.0.1:8080` instead

### "No GPU data available"

**Problem:** GPU info doesn't show on dashboard

**Solution:**
1. Click "Collect Data" button to force collection
2. Wait 2-3 seconds
3. Refresh browser page
4. If still empty, the PowerShell bridge may need initialization

### "Monitor list is empty"

**Problem:** Monitors don't show even though you have them connected

**Solution:**
1. Click "Collect Data" button
2. Wait for completion
3. Refresh browser page
4. Monitors should appear after collection completes

### Servers won't start

**Problem:** Error messages when starting backend or frontend

**Check:**
1. Are you in WSL2? (Type `wsl` if unsure)
2. Is virtual environment activated? (Should see `(venv)` in prompt)
3. Are dependencies installed? (Run `pip install -r requirements.txt` again)
4. Is database initialized? (Run `python scripts/init_database.py`)

## Normal Workflow

### Daily Use

```
1. Open Terminal 1, run backend:
   source venv/bin/activate
   python -m uvicorn backend.main:app --reload

2. Open Terminal 2, run frontend:
   python -m http.server 8080

3. Open Browser:
   http://localhost:8080

4. Use dashboard and log issues as they occur

5. When done, close both terminals (Ctrl+C)
```

### Check Patterns Weekly

```
1. Start servers (steps 1-3 above)
2. Click "Timeline" to see all incidents
3. Click "Hardware" to see driver history
4. Look for patterns (all same monitor? all after driver update?)
5. Use findings to fix the problem
```

## What the Data Tells You

### All 4 Monitors Disconnect Simultaneously
- **Likely Cause:** GPU issue, cable issue, or power issue
- **Action:** Check GPU power connectors, reseat GPU if possible

### Only Monitor 2 (LG UltraGear) Has Issues
- **Likely Cause:** Specific monitor, cable, or GPU port
- **Action:** Try different cable, try different GPU port, test monitor elsewhere

### Blackouts Started After Driver Update
- **Likely Cause:** Driver regression
- **Action:** Rollback to previous NVIDIA driver, check release notes

### Blackout Always Happens When You Move Desk
- **Likely Cause:** Loose cable from movement
- **Action:** Check DisplayPort cable is fully seated, use cable clips

### Temperature Spikes Before Blackout
- **Likely Cause:** Thermal throttling
- **Action:** Improve case airflow, clean GPU fan

## Advanced: API Documentation

While servers are running, view the full API documentation:

```
http://localhost:8000/docs
```

This shows all available endpoints you can query. You can also test them directly from the browser.

## File Structure

```
pc-inspector/
├── backend/          ← Python FastAPI server
├── frontend/         ← Web interface
├── data/
│   └── system.db     ← Database (created after init)
├── README.md         ← Project overview
├── QUICKSTART.md     ← Quick setup guide
├── MONITOR_BLACKOUT_GUIDE.md  ← Detailed debugging guide
└── START_HERE.md     ← This file
```

## Next Steps

1. **Right Now:** Start servers and log into dashboard
2. **This Week:** Click "Collect Data" to get baseline
3. **When Blackout Occurs:** Click "Log Issue"
4. **After 5+ Incidents:** Check Timeline for patterns
5. **Use Findings:** Fix the root cause based on patterns discovered

## Getting Help

If something isn't working:

1. Check that both servers are running
2. Refresh the browser page
3. Check browser console for errors (F12 → Console tab)
4. Check terminal output for error messages
5. Try the troubleshooting section above

## Tips for Best Results

1. **Log issues immediately** - While fresh in mind, add details about what happened
2. **Include context in description** - "monitor moved when I moved desk", "lasted 2 seconds", etc.
3. **Check patterns weekly** - Timeline view is most useful after multiple incidents
4. **Note driver updates** - Write down when you update GPU driver
5. **Be specific** - "All monitors" vs "just monitor 2" matters for diagnosis

## Ready?

```
1. Terminal 1: python -m uvicorn backend.main:app --reload
2. Terminal 2: python -m http.server 8080
3. Browser: http://localhost:8080
4. Click "Collect Data"
5. Start monitoring!
```

Let's debug that monitor blackout! 🔍
