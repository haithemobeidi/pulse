# PC-Inspector: One-Click Startup

No more manual terminal commands! Use these scripts to start everything with a single click.

## Choose Your Platform

### 🪟 Windows Users

#### Option 1: Batch Script (Recommended)
Double-click: `start.bat`

This will:
1. ✓ Create virtual environment (if needed)
2. ✓ Install all dependencies
3. ✓ Initialize database (if needed)
4. ✓ Start backend on port 8000
5. ✓ Start frontend on port 8080
6. ✓ Open browser to dashboard
7. ✓ Show you when everything is ready

**Two windows will open** (backend and frontend). Keep them both open while using.

#### Option 2: PowerShell Script
Right-click on `start.ps1` → Run with PowerShell

Same functionality as batch script but with better error handling.

(If PowerShell won't run scripts, you may need to enable them: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`)

### 🐧 WSL2/Linux Users

Run in terminal:
```bash
bash start.sh
```

Or make it executable and double-click:
```bash
chmod +x start.sh
./start.sh
```

This will:
1. ✓ Create virtual environment (if needed)
2. ✓ Install all dependencies
3. ✓ Initialize database (if needed)
4. ✓ Start backend in background
5. ✓ Start frontend in background
6. ✓ Open browser to dashboard
7. ✓ Tell you the PIDs to monitor

## What Happens

### ✅ First Run
Everything is set up automatically:
- Virtual environment created
- Dependencies installed
- Database initialized
- Services start

### ✅ Subsequent Runs
Much faster:
- Virtual environment already exists
- Dependencies already installed
- Database already exists
- Services start immediately

## Using the System

### Once Started

You'll see the dashboard in your browser at: **http://localhost:8080**

The services are now running:
- **Backend API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs
- **Frontend Dashboard:** http://localhost:8080

### What to Do

1. Click **"Collect Data"** to capture baseline system state
2. Go about your day normally
3. When a monitor blackout occurs:
   - Click **"Log Issue"**
   - Fill in the form
   - Submit
4. After 5+ incidents:
   - Check **"Timeline"** tab for patterns
   - Check **"Hardware"** tab for driver history
   - Use patterns to diagnose the problem

### When Done

#### Windows (Batch/PowerShell)
- Close the terminal windows
- Services will shut down automatically

#### WSL2/Bash
- Press Enter in the startup terminal
- Services will shut down automatically

## Stopping Services

### Windows
- Close the service windows that opened
- Or: Press Ctrl+C in each window
- Or: The main script window will prompt you

### WSL2/Bash
- Press Enter in the terminal where you ran `start.sh`
- Or: Open a new terminal and run:
  ```bash
  pkill -f "uvicorn"
  pkill -f "http.server"
  ```

## Troubleshooting

### Script Doesn't Work

**Windows:**
- Make sure you're in the correct directory
- Right-click `start.bat` or `start.ps1` → "Run as administrator"
- Make sure Python is installed

**WSL2/Bash:**
- Make sure you have Python 3 installed
- Try: `bash ./start.sh` instead of `./start.sh`
- Check permissions: `ls -l start.sh` should show `x`

### Services Don't Start

Check if ports are in use:
- **Windows:** Open Command Prompt and run:
  ```
  netstat -ano | findstr :8000
  netstat -ano | findstr :8080
  ```
  If something is using these ports, kill it or use different ports

- **WSL2:** Run in terminal:
  ```bash
  lsof -i :8000
  lsof -i :8080
  ```

### Dependencies Installation Fails

Try manually:
```bash
# Windows
venv\Scripts\activate.bat
pip install -r requirements.txt

# WSL2
source venv/bin/activate
pip install -r requirements.txt
```

### Browser Doesn't Open

Manual: Open browser and go to `http://localhost:8080`

### Services Started But No Data Showing

1. Wait 2 seconds (data collection takes a moment)
2. Click "Collect Data" button on dashboard
3. Refresh browser page

## Advanced: View Logs

### Windows
- Check the service windows that opened
- Error messages will display there

### WSL2
```bash
# View backend logs
tail -f /tmp/pc-inspector-backend.log

# View frontend logs
tail -f /tmp/pc-inspector-frontend.log

# View both together
tail -f /tmp/pc-inspector-*.log
```

## FAQ

**Q: Do the scripts require admin/sudo?**
A: No, they run as normal user. Only Python needs to be in PATH.

**Q: Can I customize ports?**
A: Not with the script. But you can manually edit the script or run commands directly.

**Q: What if I already have something on port 8000 or 8080?**
A: The script will fail. Use the manual commands and change ports, or stop the other service.

**Q: Do I need both terminals/windows open?**
A: Yes! One is the backend, one is the frontend. If you close either, part of the app stops working.

**Q: Can I close the startup window?**
A: No - closing it will stop the services. Keep it open while using PC-Inspector.

## Next Steps After Starting

1. **Dashboard loads** - You see your GPU and monitor info
2. **Click "Collect Data"** - Captures baseline
3. **When blackout occurs** - Click "Log Issue" button
4. **View patterns** - Check Timeline and Hardware tabs after several incidents

That's it! The app handles the rest.

---

**Enjoy your one-click PC-Inspector!** 🚀

No more terminal commands. Just run the script and start monitoring.
