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
python -m app.main %*
echo.
pause
