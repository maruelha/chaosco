@echo off
cd /d "%~dp0"

REM ---- project virtual environment (created on first run) ----
REM Keeps chaosco's packages isolated from every other Python app on this
REM machine — and keeps chaosco's pinned installs from downgrading THEIR
REM packages. The venv itself is gitignored; each machine builds its own.
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo ERROR: could not create the virtual environment. Is Python installed and in your PATH?
        pause
        exit /b 1
    )
)

echo Installing / verifying dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo.
    echo ERROR: pip install failed.
    pause
    exit /b 1
)
echo.
echo Checking for existing process on port 8010...
PowerShell -Command "Get-Process -Id (Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue).OwningProcess -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue"
echo.
echo Starting Test Coordination web server...
echo The browser will open automatically at http://127.0.0.1:8010
echo Press Ctrl+C to stop the server.
echo.
".venv\Scripts\python.exe" -m app.web
echo.
pause
