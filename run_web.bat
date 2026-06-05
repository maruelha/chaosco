@echo off
cd /d "%~dp0"
echo Starting Test Coordination web server...
echo The browser will open automatically at http://127.0.0.1:5000
echo Press Ctrl+C to stop the server.
echo.
python -m app.web
echo.
pause
