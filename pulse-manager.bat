@echo off
setlocal EnableDelayedExpansion
title Pulse Manager
color 0B

:MENU
cls
echo.
echo  ==========================================
echo       PULSE MANAGER - Server Control
echo  ==========================================
echo.

:: Check if server is running
set "RUNNING=0"
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5000 " ^| findstr "LISTENING"') do (
    set "PID=%%a"
    set "RUNNING=1"
)

if "!RUNNING!"=="1" (
    color 0A
    echo   Status:  RUNNING  [PID: !PID!]
    echo   URL:     http://localhost:5000
) else (
    color 0C
    echo   Status:  STOPPED
)

echo.
echo  ------------------------------------------
echo   [1] Start Server
echo   [2] Stop Server
echo   [3] Restart Server
echo   [4] Open in Browser
echo   [5] View Server Logs
echo   [6] Exit
echo  ------------------------------------------
echo.
set /p "choice=  Select option: "

if "%choice%"=="1" goto START
if "%choice%"=="2" goto STOP
if "%choice%"=="3" goto RESTART
if "%choice%"=="4" goto BROWSER
if "%choice%"=="5" goto LOGS
if "%choice%"=="6" goto EXIT
echo  Invalid option.
timeout /t 2 /noq >nul
goto MENU

:START
if "!RUNNING!"=="1" (
    echo.
    echo   Server is already running on PID !PID!
    timeout /t 2 /noq >nul
    goto MENU
)
echo.
echo   Starting Pulse server...
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo   ERROR: Virtual environment not found!
    echo   Run: python -m venv venv
    echo   Then: venv\Scripts\pip install -r requirements.txt
    pause
    goto MENU
)
set PYTHONPATH=%~dp0
start "Pulse Server" /min cmd /c "venv\Scripts\python.exe -m backend.app > data\server.log 2>&1"
echo   Waiting for server to start...
timeout /t 3 /noq >nul
:: Verify it started
set "RUNNING=0"
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5000 " ^| findstr "LISTENING"') do (
    set "RUNNING=1"
)
if "!RUNNING!"=="1" (
    echo   Server started successfully!
) else (
    echo   Server may have failed to start. Check logs [option 5].
)
timeout /t 2 /noq >nul
goto MENU

:STOP
if "!RUNNING!"=="0" (
    echo.
    echo   Server is not running.
    timeout /t 2 /noq >nul
    goto MENU
)
echo.
echo   Stopping server [PID: !PID!]...
taskkill /PID !PID! /F >nul 2>&1
timeout /t 1 /noq >nul
echo   Server stopped.
timeout /t 2 /noq >nul
goto MENU

:RESTART
echo.
if "!RUNNING!"=="1" (
    echo   Stopping server [PID: !PID!]...
    taskkill /PID !PID! /F >nul 2>&1
    timeout /t 2 /noq >nul
    echo   Server stopped.
)
echo   Starting Pulse server...
cd /d "%~dp0"
set PYTHONPATH=%~dp0
start "Pulse Server" /min cmd /c "venv\Scripts\python.exe -m backend.app > data\server.log 2>&1"
timeout /t 3 /noq >nul
set "RUNNING=0"
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5000 " ^| findstr "LISTENING"') do (
    set "RUNNING=1"
)
if "!RUNNING!"=="1" (
    echo   Server restarted successfully!
) else (
    echo   Server may have failed to start. Check logs [option 5].
)
timeout /t 2 /noq >nul
goto MENU

:BROWSER
start http://localhost:5000
goto MENU

:LOGS
cls
echo.
echo  ==========================================
echo       PULSE - Server Logs (last 30 lines)
echo  ==========================================
echo.
if exist "data\server.log" (
    powershell -Command "Get-Content 'data\server.log' -Tail 30"
) else (
    echo   No log file found. Start the server first.
)
echo.
echo  ------------------------------------------
echo   Press any key to return to menu...
pause >nul
goto MENU

:EXIT
exit /b 0
