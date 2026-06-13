' startup.vbs — Silent JARVIS Background Launcher
' Launches JARVIS in headless mode on Windows boot.
' No greeting fires. No window appears.
' Double-clap or phone connection will summon the GUI.
'
' To set up: Win+R → shell:startup → create shortcut to this file

Dim jarvisDir
jarvisDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

Dim shell
Set shell = CreateObject("WScript.Shell")

' Launch headless JARVIS + server (no window, no greeting)
shell.Run "py -3.11 """ & jarvisDir & "\jarvis.py"" --headless", 0, False

WScript.Quit
