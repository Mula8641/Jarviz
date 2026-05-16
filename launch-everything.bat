@echo off
REM ====================================
REM  Jarviz Voice Assistant — One Command
REM  Run this and everything installs + starts
REM ====================================

setlocal enabledelayedexpansion

echo.
echo  ██████╗ ██╗   ██╗███╗   ███╗██╗  ██╗███████╗██╗  ██╗
echo  ██╔══██╗██║   ██║████╗ ████║██║ ██╔╝██╔════╝██║  ██║
echo  ██║  ██║██║   ██║██╔████╔██║█████╔╝ █████╗  ███████║
echo  ██║  ██║██║   ██║██║╚██╔╝██║██╔═██╗ ██╔══╝  ██╔══██║
echo  ██████╔╝╚██████╔╝██║ ╚═╝ ██║██║  ██╗███████╗██║  ██║
echo  ╚═════╝  ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
echo.
echo  [Voice Assistant — Windows Installer]
echo.

REM ── Step 1: Detect Python ─────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found.
    echo  Download Python 3.10+ from https://python.org
    echo  Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

for /f "delims=" %%v in ('python -c "import sys; print(sys.version.split()[0])"') do set PYVER=%%v
echo  [OK] Python %PYVER% found

REM ── Step 2: Create virtual environment if needed ──────────────────────────
if not exist "venv" (
    echo.
    echo  [SETUP] Creating virtual environment...
    python -m venv venv
    echo  [OK] Virtual environment created
) else (
    echo  [OK] Virtual environment found
)

REM ── Step 3: Activate venv ─────────────────────────────────────────────────
set "VENV_PYTHON=venv\Scripts\python.exe"
%VENV_PYTHON% --version >nul 2>&1
if errorlevel 1 (
    echo  [WARN] venv broken — recreating...
    rmdir /s /q venv 2>nul
    python -m venv venv
)
echo  [OK] Virtual environment active

REM ── Step 4: Upgrade pip ────────────────────────────────────────────────────
echo.
echo  [INSTALL] Upgrading pip...
%VENV_PYTHON% -m pip install --upgrade pip -q
echo  [OK] Pip upgraded

REM ── Step 5: Install dependencies ─────────────────────────────────────────
echo.
echo  [INSTALL] Installing Python packages (this may take a minute)...
%VENV_PYTHON% -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo  [ERROR] Failed to install dependencies.
    echo  Try running as Administrator or check your internet connection.
    pause
    exit /b 1
)
echo  [OK] All packages installed

REM ── Step 6: Install Playwright Chromium ───────────────────────────────────
echo.
echo  [INSTALL] Downloading Chromium browser (first time only)...
%VENV_PYTHON% -m playwright install chromium 2>nul
echo  [OK] Chromium ready

REM ── Step 7: Setup config.json if missing ─────────────────────────────────
if not exist "config.json" (
    echo.
    echo  [SETUP] Creating config.json from template...
    copy config.example.json config.json >nul
    echo.
    echo  IMPORTANT: Edit config.json and add your API keys:
    echo  - minimax_api_key
    echo  - elevenlabs_api_key
    echo  - elevenlabs_voice_id
    echo.
    echo  Or set environment variables:
    echo    set MINIMAX_API_KEY=your_key
    echo    set ELEVENLABS_API_KEY=your_key
    echo    set ELEVENLABS_VOICE_ID=your_voice_id
    echo.
)

REM ── Step 8: Launch ────────────────────────────────────────────────────────
echo.
echo  ====================================
echo  Starting Voice Assistant server...
echo  Open: http://localhost:8340
echo  Press Ctrl+C to stop
echo  ====================================
echo.
%VENV_PYTHON% server.py

pause