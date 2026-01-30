# Using PC-Inspector to Debug Monitor Blackouts

This guide explains how to use PC-Inspector to diagnose your monitor blackout issue (monitor goes black when desk moves).

## The Problem

Your monitor sometimes goes black when you move your desk. This suggests:
- Loose DisplayPort/HDMI cable
- Dirty cable contacts
- Monitor port issue
- GPU port issue
- Driver-related display error

## How PC-Inspector Helps

Instead of guessing, PC-Inspector captures the **exact system state when blackouts occur**, allowing you to:
1. See which monitor(s) had the issue
2. Check GPU driver version at that time
3. Verify monitor connection type (DisplayPort vs HDMI)
4. Detect patterns (always same monitor? always after driver update?)
5. Provide detailed information to support if needed

## Setup (First Time)

### 1. Start Backend Server

```bash
cd "C:\Users\haith\Documents\Vibe Projects\pc-inspector"
venv\Scripts\activate  # On Windows
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Keep this running in the background.

### 2. Start Frontend Server

```bash
cd "C:\Users\haith\Documents\Vibe Projects\pc-inspector\frontend"
python -m http.server 8080
```

### 3. Open Dashboard

Open browser: `http://localhost:8080`

You should see:
- GPU Status (RTX 5090, Driver version)
- Monitors (3x LG UltraGear + Alienware)
- Memory and CPU info
- Recent Issues section

## When a Blackout Occurs

### Immediate Action (while blackout fresh in mind)

1. **After monitor comes back**, open `http://localhost:8080` in browser
2. Click **"Log Issue"** button
3. Fill in the form:
   ```
   Issue Type: Monitor Blackout
   Severity: High
   Description: "Monitor went black when I moved desk to the right,
                lasted ~2 seconds, then came back. All 3 monitors
                affected / only Monitor 2 affected?"
   ```
4. Click **"Log Issue"** button

System will:
- Create snapshot of exact system state
- Capture GPU driver version
- Record all monitor details
- Store timestamp

### What Gets Captured

When you log an issue:
```
Snapshot captured:
- GPU: RTX 5090
- Driver: 591.74 (exact version)
- Temperature: 65°C
- Monitor 1: LG UltraGear (DisplayPort, connected)
- Monitor 2: LG UltraGear (DisplayPort, connected)
- Monitor 3: LG UltraGear (DisplayPort, connected)
- Monitor 4: Alienware AW3425DW (DisplayPort, connected)
- CPU: Intel Core i7
- Memory: 32GB
- Timestamp: 2026-01-30 14:32:15
```

## Analysis

### After Several Incidents (5+ blackouts)

Click **"Hardware"** tab to see patterns:

**GPU History:**
- Shows all driver versions over time
- If all blackouts happened with Driver 591.74, that's a clue
- If they happened right after an update, driver might be issue

**Monitor History:**
- Shows connection type consistency
- If Monitor 2 always shows disconnected then reconnected, that's the problem monitor
- DisplayPort vs HDMI difference is clear

### Timeline View

Click **"Timeline"** tab:
- See all blackout events chronologically
- See when they occurred
- Spot patterns:
  - "3 blackouts in one hour" = active use issue
  - "One blackout per day" = thermal issue?
  - "Blackout exactly after driver update" = driver bug?

### All Issues

Click **"Issues"** tab:
- Complete list of every blackout logged
- Each one links to full system state at that time
- Can compare system state before/after a blackout

## Next Steps Based on Findings

### If All Monitors Show Disconnection Simultaneously
**Likely Cause:** GPU issue or main cable
**Action:**
- Check GPU power connections
- Reseat GPU if applicable
- Test with different cable

### If Only Monitor 2 Has Issues
**Likely Cause:** Cable, monitor port, or GPU port
**Action:**
- Replace DisplayPort cable for Monitor 2
- Try Monitor 2 in different GPU port
- Clean cable contacts with isopropyl alcohol

### If Blackouts Started After Driver Update
**Likely Cause:** Driver regression
**Action:**
- Rollback to previous driver version
- Check NVIDIA release notes for display fixes
- Monitor if next driver fixes it

### If Blackouts Correlate with High GPU Temperature
**Likely Cause:** Thermal throttling or power delivery issue
**Action:**
- Improve case airflow
- Clean GPU
- Check power supply capacity

### If Blackouts Happen Only When Desk Moves
**Likely Cause:** Physical connection looseness
**Action:**
- Check all DisplayPort cables are fully seated
- Ensure GPU power cables are tight
- Consider cable management clips to reduce movement

## Export Data

When ready to contact NVIDIA or monitor support:

1. Go to "Issues" tab
2. Copy issue descriptions with exact error details
3. Go to "Hardware" tab
4. Note GPU driver version when issue occurred
5. Screenshot Timeline showing the pattern

Provide them with:
- "Monitor blackout occurred with driver 591.74"
- "3 incidents, always Monitor 2 (DisplayPort)"
- "Pattern shows disconnection recovery each time"
- Timestamps of incidents

## Pro Tips

1. **Log immediately after incident** - While fresh in mind, add details
   - "Lasted 2 seconds"
   - "All monitors or just one?"
   - "Was I moving the desk?"

2. **Add notes to description**
   - "Started after driver update to 591.74"
   - "Monitor came back automatically"
   - "Took 30 seconds to recover"

3. **Check patterns weekly**
   - Open Timeline to spot trends
   - Check if driver updates correlate
   - Identify which monitor is problematic

4. **Use "Collect Data" button**
   - When blackout happens frequently, collect a snapshot
   - Even if not during issue, captures baseline state
   - Useful for comparison

## Hardware Status Interpretation

### Dashboard Shows:
```
GPU Status:
  GPU: NVIDIA RTX 5090
  Driver: 591.74                    ← Watch for changes
  VRAM: 24576 MB
  Temperature: 65°C                 ← High temps = instability risk

Monitors:
  Count: 4
  LG UltraGear: DisplayPort         ← Connection type
  LG UltraGear: DisplayPort
  LG UltraGear: DisplayPort
  Alienware AW3425DW: DisplayPort
```

### What to Watch For:
- **Driver changes**: Note when driver updates occur
- **Temperature spikes**: High temps before blackouts = thermal issue
- **Monitor disconnections**: In history, shows reconnection pattern
- **Connection type consistency**: All should be same type (all DP or all HDMI)

## Troubleshooting PC-Inspector

### Can't connect to dashboard
```
Check:
1. Backend running? (port 8000)
   http://localhost:8000/docs should show API docs

2. Frontend running? (port 8080)
   http://localhost:8080 should show dashboard

3. Firewall blocking? Allow localhost connections
```

### Issues not saving
```
Check:
1. Database exists: data/system.db should be 120KB+
2. Backend logs show errors?
3. Browser console shows network errors?
```

### GPU info not appearing
```
Check:
1. PowerShell access working?
   Run backend with verbose logging

2. NVIDIA driver installed? Check Device Manager

3. Try manual collection:
   Click "Collect Data" button on dashboard
```

## FAQ

**Q: Will this slow down my PC?**
A: No. Data collection runs for ~1 second, only when triggered. Frontend is lightweight.

**Q: How much disk space does it use?**
A: Database grows ~1KB per snapshot. 1000 snapshots = 1MB. Very efficient.

**Q: Can it predict when blackout will happen?**
A: Phase 2 will add correlation analysis. Currently it documents what happened.

**Q: Should I keep servers running 24/7?**
A: No, just start when you want to collect data. Optional background scheduler coming in Phase 2.

**Q: Can I export data?**
A: Yes, database is standard SQLite. In Phase 2, will add proper export. For now, can use SQLite browser.

**Q: What if I don't see all 4 monitors?**
A: Disconnected monitors may not appear. Will show connected ones. Try "Collect Data" after reconnecting.

## Next Phase Features (Coming Soon)

- [ ] Automatic periodic snapshots (every 4 hours)
- [ ] Pattern correlation engine
- [ ] "Blackout likely caused by..." recommendations
- [ ] Windows Event Log integration (display driver errors)
- [ ] Automatic driver update detection
- [ ] Export to PDF/Excel for support tickets
- [ ] Real-time monitoring dashboard
- [ ] Thermal history graphs

## Contact & Support

Current MVP provides:
- ✓ Full system state capture
- ✓ Timeline visualization
- ✓ Issue logging and retrieval
- ✓ Hardware history tracking

For feature requests or issues, the codebase is fully documented and extensible.

---

**Start monitoring your monitor blackouts now!**

1. Start both servers
2. Open dashboard
3. Click "Collect Data" to get baseline
4. Next blackout → Click "Log Issue"
5. After 5-10 incidents → Check Timeline for patterns
6. Use findings to fix the root cause
