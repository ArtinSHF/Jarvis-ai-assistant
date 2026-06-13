@echo off
:: ─────────────────────────────────────────────────────────────────────────────
:: build_launcher.bat — Compile launcher.py → JARVIS.exe
:: Run this from the JARVIS project folder using your REGULAR Python 3.11
:: (not the embedded one — this only needs to run once during packaging)
:: ─────────────────────────────────────────────────────────────────────────────

echo.
echo  ================================================================
echo   JARVIS Launcher Builder
echo  ================================================================
echo.

:: Install PyInstaller into your regular Python if not already there
echo  [1/3] Checking PyInstaller...
py -3.11 -m pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo  Installing PyInstaller...
    py -3.11 -m pip install pyinstaller
) else (
    echo  PyInstaller already installed.
)

echo.
echo  [2/3] Compiling launcher.py to JARVIS.exe...
echo         (This takes about 30 seconds)
echo.

:: --onefile    = single .exe, no folder
:: --noconsole  = no black CMD window when launched
:: --name JARVIS = output is called JARVIS.exe
:: --clean      = fresh build every time
py -3.11 -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --name JARVIS ^
    --clean ^
    launcher.py

if %errorlevel% neq 0 (
    echo.
    echo  [!] Build FAILED. Check the errors above.
    pause
    exit /b 1
)

echo.
echo  [3/3] Copying JARVIS.exe to project root...
copy /Y "dist\JARVIS.exe" "JARVIS.exe"

:: Clean up PyInstaller build artifacts
echo  Cleaning up build artifacts...
rmdir /S /Q dist
rmdir /S /Q build
del /Q JARVIS.spec

echo.
echo  ================================================================
echo   Done! JARVIS.exe is ready in this folder.
echo.
echo   Next steps:
echo   1. Make sure ./python/ exists (run setup_package.py first)
echo   2. Double-click JARVIS.exe to launch
echo  ================================================================
echo.
pause
