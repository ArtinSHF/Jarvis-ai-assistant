@echo off
:: ─────────────────────────────────────────────────────────────────────────────
:: debug_launch.bat — Run JARVIS with full error output visible
:: Use this whenever JARVIS.exe silently crashes to see the actual error.
:: ─────────────────────────────────────────────────────────────────────────────

cd /d "%~dp0"

echo.
echo  ================================================================
echo   JARVIS Debug Launch
echo   All errors will be shown below.
echo   Window stays open after crash so you can read the error.
echo  ================================================================
echo.

if not exist "python\python.exe" (
    echo  [ERROR] python\python.exe not found.
    echo  Run setup_package.py first.
    pause
    exit /b 1
)

if not exist "jarvis.py" (
    echo  [ERROR] jarvis.py not found in this folder.
    echo  Make sure all JARVIS files are here alongside JARVIS.exe.
    pause
    exit /b 1
)

echo  Launching jarvis.py via embedded Python...
echo  ----------------------------------------------------------------
echo.

python\python.exe jarvis.py

echo.
echo  ----------------------------------------------------------------
echo  JARVIS exited with code: %errorlevel%
echo  ----------------------------------------------------------------
pause
