@echo off
cd /d "%~dp0"
set JARVIS_DIR=%~dp0
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set VBS_FILE=%TEMP%\make_shortcut.vbs

echo Set oWS = WScript.CreateObject("WScript.Shell") > "%VBS_FILE%"
echo sLinkFile = "%STARTUP%\JARVIS_Listener.lnk" >> "%VBS_FILE%"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%VBS_FILE%"
echo oLink.TargetPath = "py" >> "%VBS_FILE%"
echo oLink.Arguments = "-3.11 ""%JARVIS_DIR%clap_listener.py""" >> "%VBS_FILE%"
echo oLink.WorkingDirectory = "%JARVIS_DIR%" >> "%VBS_FILE%"
echo oLink.WindowStyle = 7 >> "%VBS_FILE%"
echo oLink.Save >> "%VBS_FILE%"

cscript //nologo "%VBS_FILE%"
del "%VBS_FILE%"

echo.
echo [JARVIS] Auto-startup configured!
echo [JARVIS] Clap listener will now start automatically when Windows boots.
echo [JARVIS] To remove: delete "JARVIS_Listener.lnk" from your Startup folder.
echo.
pause
