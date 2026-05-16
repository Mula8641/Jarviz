@echo off
REM Jarviz Voice Assistant — Launch Everything
REM Run this to start all services at once

echo ====================================
echo  Jarviz — Launching Everything
echo ====================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ first.
    pause
    exit /b 1
)

REM Install deps if needed
echo [1/3] Checking dependencies...
pip install -r requirements.txt >nul 2>&1
echo  Deps OK

REM Install Playwright browser
echo [2/3] Installing Chromium...
playwright install chromium >nul 2>&1
echo  Chromium OK

REM Launch server
echo [3/3] Starting Voice Assistant server...
echo.
echo  Server running at http://localhost:8340
echo  Press Ctrl+C to stop
echo.

REM Start server and wait
python server.py

pause