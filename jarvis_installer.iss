; jarvis_installer.iss — JARVIS Inno Setup Installer Script
; =============================================================================
; Requires: Inno Setup 6  →  https://jrsoftware.org/isdl.php  (free, ~5MB)
;
; How to build:
;   1. Drop this file into your JARVIS project folder (same level as JARVIS.exe)
;   2. Open it — Inno Setup Compiler launches automatically
;   3. Tools > Generate GUID → paste it over YOUR-GUID-HERE below
;   4. Press Ctrl+F9 to compile
;   5. Grab Output\JARVIS_Setup_1.0.0.exe  — send it to anyone
; =============================================================================

#define AppName      "J.A.R.V.I.S"
#define AppVersion   "1.0.0"
#define AppExeName   "JARVIS.exe"
#define AppPublisher "Artin"

; ── [Setup] ──────────────────────────────────────────────────────────────────
[Setup]
; IMPORTANT: generate your own GUID via Tools > Generate GUID in Inno Setup
; and replace the line below. This ID identifies your app for Windows.
AppId={{1E149CFC-FFEE-4136-B5B3-3DDFCDCF499F}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}

; Install to user's AppData\Local — no admin rights needed on any PC
DefaultDirName={localappdata}\Programs\JARVIS
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes

; Output
OutputDir=Output
OutputBaseFilename=JARVIS_Setup_{#AppVersion}

; Compression — lzma2 makes the installer as small as possible
; ultra64 is slowest to build but produces smallest file (~60% size reduction)
Compression=lzma2/ultra64
SolidCompression=yes
CompressionThreads=auto

; UI style
WizardStyle=modern
DisableWelcomePage=no

; No admin required — installs per-user
PrivilegesRequired=lowest

; Uninstaller
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
CreateUninstallRegKey=yes


; ── [Languages] ──────────────────────────────────────────────────────────────
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"


; ── [Tasks] ──────────────────────────────────────────────────────────────────
; These show up as checkboxes during install
[Tasks]
; Desktop shortcut — checked by default (default behaviour, no flag needed)
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "{cm:AdditionalIcons}"

; Windows startup — unchecked by default (user opts in)
; Starts JARVIS hidden on boot, waits for double-clap to show UI
Name: "startup"; Description: "Start JARVIS automatically with Windows (runs hidden, press double-clap to wake)"; GroupDescription: "Windows startup:"; Flags: unchecked


; ── [Files] ──────────────────────────────────────────────────────────────────
; Everything gets copied to the install folder chosen by the user.
; NOTE: jarvis_settings.json is intentionally NOT included — settings live
; in %APPDATA%\JARVIS\ and survive installs, updates, and uninstalls.
[Files]
; Launcher executable
Source: "JARVIS.exe";               DestDir: "{app}"; Flags: ignoreversion

; Core Python scripts
Source: "jarvis.py";                DestDir: "{app}"; Flags: ignoreversion
Source: "brain.py";                 DestDir: "{app}"; Flags: ignoreversion
Source: "server.py";                DestDir: "{app}"; Flags: ignoreversion
Source: "task_executor.py";         DestDir: "{app}"; Flags: ignoreversion
Source: "clap_listener.py";         DestDir: "{app}"; Flags: ignoreversion
Source: "screen_watcher.py";        DestDir: "{app}"; Flags: ignoreversion
Source: "notification_listener.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "reminder_engine.py";       DestDir: "{app}"; Flags: ignoreversion
Source: "spotify_helper.py";        DestDir: "{app}"; Flags: ignoreversion
Source: "settings.py";              DestDir: "{app}"; Flags: ignoreversion
Source: "notes.py";                 DestDir: "{app}"; Flags: ignoreversion
Source: "sfx.py";                   DestDir: "{app}"; Flags: ignoreversion

; Auto-updater (Phase 3)
Source: "updater.py";               DestDir: "{app}"; Flags: ignoreversion
Source: "version.txt";              DestDir: "{app}"; Flags: ignoreversion

; UI files
Source: "index.html";               DestDir: "{app}"; Flags: ignoreversion
Source: "mobile.html";              DestDir: "{app}"; Flags: ignoreversion
Source: "call_mode.html";           DestDir: "{app}"; Flags: ignoreversion

; Embedded Python + all installed packages
; This is the big one — copies the entire python\ folder recursively
Source: "python\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs


; ── [Icons] ──────────────────────────────────────────────────────────────────
[Icons]
; Start Menu entry
Name: "{group}\{#AppName}";           Filename: "{app}\{#AppExeName}"; Comment: "Launch J.A.R.V.I.S"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

; Desktop shortcut (only if user checked the box)
Name: "{autodesktop}\{#AppName}";     Filename: "{app}\{#AppExeName}"; Tasks: desktopicon; Comment: "Launch J.A.R.V.I.S"


; ── [Registry] ───────────────────────────────────────────────────────────────
[Registry]
; Startup registry key — only written if user checked the startup task
; Runs JARVIS.exe --headless on boot (UI is hidden until double-clap)
; uninsdeletevalue = automatically removed when JARVIS is uninstalled
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "JARVIS"; ValueData: """{app}\{#AppExeName}"" --headless"; Flags: uninsdeletevalue; Tasks: startup


; ── [Run] ────────────────────────────────────────────────────────────────────
[Run]
; Offer to launch JARVIS immediately after install finishes
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent


; ── [Code] ───────────────────────────────────────────────────────────────────
; Pascal script — handles the AppData cleanup question on uninstall
[Code]

// Ask the user whether to delete their settings/logs from AppData when
// uninstalling. Default answer is NO so they keep their API keys if they
// decide to reinstall later.
function InitializeUninstall(): Boolean;
var
  AppDataDir : String;
  Res        : Integer;
begin
  Result     := True;
  AppDataDir := ExpandConstant('{userappdata}\JARVIS');

  if DirExists(AppDataDir) then
  begin
    Res := MsgBox(
      'Do you want to delete your JARVIS settings and data?' + #13#10 +
      '(API keys, preferences, and logs stored in AppData\JARVIS)' + #13#10 + #13#10 +
      'YES  →  delete everything (clean wipe)' + #13#10 +
      'NO   →  keep settings so you can reinstall later',
      mbConfirmation,
      MB_YESNO
    );

    if Res = IDYES then
      DelTree(AppDataDir, True, True, True);
  end;
end;

// Show a message after install reminding where to put API keys
// since there's no jarvis_settings.json bundled in the installer.
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssDone then
  begin
    MsgBox(
      'JARVIS installed successfully!' + #13#10 + #13#10 +
      'First launch: open JARVIS and go to the Settings menu to enter your API keys.' + #13#10 +
      '(Gemini, Spotify, Steam — your settings are saved in AppData and will' + #13#10 +
      'survive future updates and reinstalls.)',
      mbInformation,
      MB_OK
    );
  end;
end;
