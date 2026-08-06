@echo off
cd /d "%~dp0"

REM ---- project virtual environment (created on first run) ----
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
".venv\Scripts\python.exe" -m app.main %*
echo.
pause
