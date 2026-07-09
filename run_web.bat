@echo off
cd /d "%~dp0"
echo Installing / verifying dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo.
    echo ERROR: pip install failed. Is Python installed and in your PATH?
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
python -m app.web
echo.
pause
