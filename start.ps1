# PC-Inspector - One-Click Startup Script for PowerShell

param(
    [switch]$NoOpen
)

# Get the script directory
$ScriptDir = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════╗"
Write-Host "║           PC-INSPECTOR - Starting Services                    ║"
Write-Host "╚════════════════════════════════════════════════════════════════╝"
Write-Host ""

# Check if venv exists
if (-not (Test-Path "venv")) {
    Write-Host "[1/4] Creating Python virtual environment..."
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to create virtual environment"
        Write-Host "Make sure Python 3.12 is installed and in PATH"
        Read-Host "Press Enter to exit"
        exit 1
    }
}

# Activate venv and install dependencies
Write-Host "[2/4] Installing dependencies..."
& ".\venv\Scripts\Activate.ps1"
pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to install dependencies"
    Read-Host "Press Enter to exit"
    exit 1
}

# Initialize database
if (-not (Test-Path "data\system.db")) {
    Write-Host "[3/4] Initializing database..."
    python scripts\init_database.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to initialize database"
        Read-Host "Press Enter to exit"
        exit 1
    }
} else {
    Write-Host "[3/4] Database already initialized"
}

# Start services
Write-Host "[4/4] Starting services..."
Write-Host ""
Write-Host "Starting Backend (FastAPI) on http://localhost:8000"

# Start backend in new PowerShell window
$backendProcess = Start-Process powershell -ArgumentList @"
  Set-Location '$ScriptDir'
  .\venv\Scripts\Activate.ps1
  python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
"@ -PassThru -WindowStyle Normal

Start-Sleep -Seconds 2

Write-Host "Starting Frontend (HTTP Server) on http://localhost:8080"

# Start frontend in new PowerShell window
$frontendProcess = Start-Process powershell -ArgumentList @"
  Set-Location '$ScriptDir\frontend'
  python -m http.server 8080
"@ -PassThru -WindowStyle Normal

Start-Sleep -Seconds 2

# Display status
Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════╗"
Write-Host "║             Services Started Successfully!                    ║"
Write-Host "╚════════════════════════════════════════════════════════════════╝"
Write-Host ""
Write-Host "Dashboard:  http://localhost:8080"
Write-Host "API Docs:   http://localhost:8000/docs"
Write-Host ""
Write-Host "Two service windows will open:"
Write-Host "  1. Backend (FastAPI on port 8000)"
Write-Host "  2. Frontend (HTTP server on port 8080)"
Write-Host ""
Write-Host "Keep both windows open while using PC-Inspector"
Write-Host ""

# Open browser
if (-not $NoOpen) {
    Write-Host "Opening dashboard in browser..."
    Start-Process "http://localhost:8080"
}

# Wait for user to press Enter
Write-Host ""
Read-Host "Press Enter to stop services and exit"

# Stop processes
Write-Host ""
Write-Host "Shutting down services..."
Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $frontendProcess.Id -Force -ErrorAction SilentlyContinue
Write-Host "Services closed. Goodbye!"
