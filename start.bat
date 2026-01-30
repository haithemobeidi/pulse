@echo off
REM PC-Inspector - One-Click Startup Script for Windows

setlocal enabledelayedexpansion

REM Get the directory where this script is located
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

REM Colors for output
for /F %%A in ('copy /Z "%~f0" nul') do set "BS=%%A"

echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║           PC-INSPECTOR - Starting Services                    ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

REM Check if venv exists
if not exist "venv\" (
    echo [1/4] Creating Python virtual environment...
    python -m venv venv
    if !errorlevel! neq 0 (
        echo Error: Failed to create virtual environment
        echo Make sure Python 3.12 is installed and in PATH
        pause
        exit /b 1
    )
)

REM Activate venv and install dependencies
echo [2/4] Installing dependencies...
call venv\Scripts\activate.bat
pip install -q -r requirements.txt
if !errorlevel! neq 0 (
    echo Error: Failed to install dependencies
    pause
    exit /b 1
)

REM Initialize database
if not exist "data\system.db" (
    echo [3/4] Initializing database...
    python scripts\init_database.py
    if !errorlevel! neq 0 (
        echo Error: Failed to initialize database
        pause
        exit /b 1
    )
) else (
    echo [3/4] Database already initialized
)

REM Start backend in new window
echo [4/4] Starting services...
echo.
echo Starting Backend (FastAPI) on http://localhost:8000
start "PC-Inspector Backend" cmd /k "cd /d "%SCRIPT_DIR%" && venv\Scripts\activate.bat && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"

REM Give backend time to start
timeout /t 2 /nobreak

REM Start frontend in new window
echo Starting Frontend (HTTP Server) on http://localhost:8080
cd frontend
start "PC-Inspector Frontend" cmd /k "cd /d "%SCRIPT_DIR%\frontend" && python -m http.server 8080"

REM Return to main directory
cd /d "%SCRIPT_DIR%"

REM Wait a moment for servers to start
timeout /t 2 /nobreak

REM Open browser
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║             Services Started Successfully!                    ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.
echo Opening dashboard in browser...
echo.
echo Dashboard:  http://localhost:8080
echo API Docs:   http://localhost:8000/docs
echo.
echo Two service windows will open:
echo   1. Backend (FastAPI on port 8000)
echo   2. Frontend (HTTP server on port 8080)
echo.
echo Keep both windows open while using PC-Inspector
echo Close them when finished
echo.

REM Try to open browser
start http://localhost:8080

REM Keep this window open
echo Press any key to exit (this closes both services)...
pause
echo.
echo Shutting down services...
taskkill /FI "WINDOWTITLE eq PC-Inspector*" /T /F >nul 2>&1
echo Services closed. Goodbye!
