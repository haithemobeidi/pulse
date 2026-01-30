@echo off
REM PC-Inspector - One-Click Startup Script for Windows
REM Simplified version that avoids activation issues

setlocal enabledelayedexpansion

REM Get the directory where this script is located
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo.
echo PC-INSPECTOR - Starting Services
echo.

REM Create venv if it doesn't exist
if not exist "venv" (
    echo [1/4] Creating Python virtual environment...
    python -m venv venv
    if !errorlevel! neq 0 (
        echo ERROR: Failed to create virtual environment
        echo Make sure Python 3.12+ is installed and in your PATH
        pause
        exit /b 1
    )
)

REM Install dependencies using venv's pip directly
echo [2/4] Installing dependencies...
venv\Scripts\pip install -q -r requirements.txt >nul 2>&1
if !errorlevel! neq 0 (
    echo WARNING: Some dependencies may not have installed
    echo Attempting again with verbose output...
    venv\Scripts\pip install -r requirements.txt
)

REM Initialize database
if not exist "data\system.db" (
    echo [3/4] Initializing database...
    venv\Scripts\python scripts\init_database.py
    if !errorlevel! neq 0 (
        echo ERROR: Failed to initialize database
        pause
        exit /b 1
    )
) else (
    echo [3/4] Database already initialized
)

REM Start backend
echo [4/4] Starting services...
echo.
echo Starting Backend on http://localhost:8000
start "PC-Inspector Backend" venv\Scripts\python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

timeout /t 3 /nobreak

REM Start frontend
echo Starting Frontend on http://localhost:8080
start "PC-Inspector Frontend" cmd /k "cd /d "%SCRIPT_DIR%frontend" & python -m http.server 8080"

timeout /t 2 /nobreak

REM Display info
echo.
echo ========================================
echo Services Started!
echo.
echo Dashboard:  http://localhost:8080
echo API Docs:   http://localhost:8000/docs
echo.
echo Two windows will be open. Keep them both running.
echo ========================================
echo.

REM Open browser
start http://localhost:8080

REM Wait for user
echo Press Enter to stop services and exit...
pause

echo.
echo Shutting down...
taskkill /FI "WINDOWTITLE eq PC-Inspector*" /T /F 2>nul
echo Done!
