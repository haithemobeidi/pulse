@echo off
title Pulse - Starting...
color 0A
echo.
echo  ========================================
echo       PULSE - PC Troubleshooting
echo  ========================================
echo.
echo  Starting server...
echo.

cd /d "%~dp0"

:: Check if venv exists
if not exist "venv\Scripts\python.exe" (
    color 0C
    echo  ERROR: Virtual environment not found!
    echo  Run: python -m venv venv
    echo  Then: venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

:: Start the server
echo  Server starting on http://localhost:5000
echo  Press Ctrl+C to stop
echo.

:: Open browser after a short delay
start /b cmd /c "timeout /t 3 /noq >nul && start http://localhost:5000"

:: Run Flask with venv Python
set PYTHONPATH=%~dp0
venv\Scripts\python.exe -m backend.app
