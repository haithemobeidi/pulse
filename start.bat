@echo off
REM PC-Inspector - One-Click Startup
REM Simple Flask app - single command, everything included

setlocal enabledelayedexpansion
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo.
echo PC-Inspector Starting...
echo.

REM Create venv if needed
if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
)

REM Install dependencies
echo Installing dependencies...
venv\Scripts\pip install -q -r requirements.txt

REM Initialize database
if not exist "data\system.db" (
    echo Initializing database...
    venv\Scripts\python scripts\init_database.py
)

REM Start Flask app
echo.
echo ========================================
echo PC-Inspector is starting...
echo Dashboard: http://localhost:5000
echo ========================================
echo.

venv\Scripts\python -m backend.app
