# J.A.R.V.I.S — Custom AI Desktop Assistant

> *Just A Rather Very Intelligent System* — a fully custom AI desktop assistant built from scratch with Python, Google Gemini, a cyberpunk UI, voice I/O, screen awareness, mobile mirroring, and autonomous task execution.

<img width="1917" height="1012" alt="screenshot 1" src="https://github.com/user-attachments/assets/0ff19a31-6546-4f8b-a4a1-e460a0cfb4e2" />

---

## What Is This?

JARVIS is a personal AI assistant I built entirely from scratch as an ongoing solo project. It runs as a cyberpunk desktop interface, listens for voice input, watches the screen in the background, reads notifications aloud, controls apps and music, mirrors itself to a phone, and can autonomously execute large multi-step coding or file tasks — all without touching a single third-party assistant framework.

Every subsystem — the brain, the voice pipeline, the mobile server, the agent engine, the screen watcher, the settings manager, the installer, and the auto-updater — was designed and written by me.

This is not a wrapper around an existing assistant. It is a ground-up implementation.

---

## 🧠 What I Learned Building This

This section exists for anyone evaluating this project from a technical or hiring perspective.

### AI & Prompt Engineering
- Designed a multi-turn conversation system using the Gemini API directly via REST, without SDK wrappers
- Built a structured JSON planner prompt that instructs Gemini to return executable step plans (autonomous agent mode)
- Engineered dynamic system prompts that inject personality modifiers, conversation memory, and screen context at runtime
- Designed a screen reaction prompt system that forces format variety across 6 distinct reaction styles and prevents repeated outputs using last-reaction injection
- Tuned probabilistic gating, interest boost systems, and cooldown logic to make AI reactions feel natural rather than robotic

### Backend & Systems Programming
- Built a Flask-SocketIO server for real-time bidirectional communication between the PC and a mobile mirror UI
- Implemented RAM-only TTS audio using `io.BytesIO` — no temp files written to disk at any point
- Designed a threaded task queue system so JARVIS can process and queue multiple commands without blocking
- Built an autonomous agent engine that parses a Gemini-generated JSON plan and executes `mkdir`, `write_file`, `run_cmd`, and `delete_file` operations sequentially with live UI feedback
- Wrote a Windows notification reader that copies a locked SQLite database (`wpndatabase.db`) to a temp path to bypass Windows exclusive file locks, queries it, and filters results
- Implemented Wake-on-LAN magic packet sending from scratch using raw UDP sockets

### Distribution & Packaging
- Bundled a self-contained embedded Python 3.11 environment so the app runs on any Windows PC with zero prerequisites
- Built a compiled `JARVIS.exe` launcher using PyInstaller that finds and boots the embedded Python — no system Python required
- Wrote a complete Inno Setup installer script that handles install path selection, desktop shortcuts, Start Menu entries, optional Windows startup registration, and an uninstaller with AppData cleanup prompt
- Migrated all user settings and API keys to `%APPDATA%\JARVIS\` so they survive every install, update, and reinstall without ever being wiped
- Built a GitHub Releases auto-updater that checks for new versions on every launch, downloads only the code zip (~50–100KB), extracts in-memory, and restarts JARVIS automatically — users never manually update

### Audio & Voice
- Integrated `SpeechRecognition` with `PyAudio` for microphone-based voice input with ambient noise adjustment
- Built a double-clap detection system using RMS spike analysis on a live audio stream via `PyAudio`
- Implemented Edge-TTS voice output with a queued worker thread so speech never blocks the main loop
- Handled `pygame` version differences by detecting `BytesIO` support and falling back to a load-and-immediately-delete temp file strategy

### Frontend & UI
- Built a full cyberpunk desktop UI in HTML/CSS/JS rendered inside a `pywebview` native window
- Designed a separate floating call mode window with its own JS API bridge
- Built a mobile companion UI in `mobile.html` that mirrors the desktop assistant via SocketIO
- Implemented a live screenshot viewer on the phone that polls `/screenshot` at ~5fps using a JPEG stream
- Built a multi-line auto-resizing textarea input where Enter sends and Shift+Enter inserts a newline
- Built a fullscreen agent mode overlay with live step logging and animated status indicators

### Security & Settings Architecture
- Designed a settings system with a `PROTECTED_KEYS` frozenset — API keys and user calibration values never get overwritten on update or restart
- Non-destructive startup reset: only adds new default keys introduced by updates, never touches existing user config
- Removed all secrets from source code — credentials load from `%APPDATA%\JARVIS\jarvis_settings.json` which is gitignored
- Implemented token-based auth on all server endpoints and SocketIO connections

### Windows Integration
- Used `ctypes`, `pyautogui`, `psutil`, `win32gui`, `win32con`, and `win32process` for window management, brightness control, volume control, and foreground window detection
- Built screen capture using `mss` entirely in RAM (640×360 JPEG in `BytesIO`, never written to disk)
- Implemented a VBS headless startup launcher so JARVIS boots silently with Windows and waits for a double-clap or phone connection before showing the UI

---

## ✨ Features

### Core Assistant
- Cyberpunk desktop UI (pywebview + HTML/CSS/JS)
- Floating call mode window
- Multi-line chat input (Enter to send, Shift+Enter for newline)
- Voice input and output
- App open/close, window switching, window listing
- Volume and brightness control
- Power commands (shutdown, restart, sleep, lock)
- PC stats (CPU, RAM, disk, top processes)
- Notes system (add, read, clear)
- Timers and reminders (one-time, daily, weekdays, weekends)
- Daily briefings

### Voice System
- Microphone-based speech recognition
- Edge-TTS voice output (en-GB-RyanNeural by default)
- TTS generated entirely in RAM — no temp files
- Queued TTS worker thread — speech never blocks commands
- Double-clap activation using RMS/spike detection on live audio

### Screen Awareness
- Background screen watcher using Gemini Vision
- Probabilistic gating + interest boost system keeps reactions rare and natural
- Configurable check interval, reaction probability, and cooldown gap
- 6 distinct reaction styles with last-reaction injection to force variety
- Screen OCR — reads all visible text aloud
- Screen translation — detects language and translates to English
- Context-aware Spotify — reads screen, picks a fitting playlist automatically
- All captures in-memory only, nothing written to disk
- Skips reactions when the JARVIS window is focused

### Notification Reader
- Polls Windows notification database (`wpndatabase.db`) every 3 seconds
- Copies locked DB to a temp path to bypass Windows file lock
- Filters by configurable app whitelist
- Strips XML payload to readable text, skips spam
- Reads qualifying notifications aloud and injects them into conversation history

### Autonomous Agent Mode
- Detects large task prompts (≥500 chars or task marker tags)
- Sends the full prompt to Gemini with a structured JSON planner system prompt
- Gemini returns a step plan: `mkdir`, `write_file`, `run_cmd`, `delete_file`
- Executes every step sequentially with live progress in a fullscreen overlay
- Locks all user input while the task runs, unlocks and notifies on completion
- All paths resolved through env var expansion and a default working directory

### Personality Modes
- Four modes: Normal, Professional, Casual, Unhinged
- Each injects a short modifier into the Gemini system prompt on every call
- Configurable in the settings UI, takes effect immediately

### Session Memory
- All JARVIS-initiated messages (screen reactions, notifications, reminders, briefings, agent completions) are injected into the Gemini conversation array
- Conversation capped at 40 pairs to keep RAM bounded
- Session-only — resets on restart, no files written

### Mobile Mirror
- Flask-SocketIO server accessible over local Wi-Fi or Tailscale
- Mobile UI mirrors the desktop assistant interface
- Live screenshot viewer polls `/screenshot` at ~5fps (read-only)
- TTS audio streamed to phone as base64 via Web Audio API
- Token-based auth on all endpoints
- Ghost mode suppresses Windows S0 Modern Standby to keep server alive

### Spotify Control
- Play songs, artists, playlists by name
- Open liked songs
- Check what is currently playing (reads Spotify window title — no API key needed for this)
- Music sleep timer
- Context-aware vibe mode based on screen content

### Steam Integration
- Launch games by name
- Check game hours
- View friends online
- Check if a game is on sale (queries Steam store API)

---

## 🏗 Architecture Overview

```
jarvis.py                — Entry point, pywebview window, startup reset
brain.py                 — Gemini, TTS queue, command execution, session memory
server.py                — Flask-SocketIO mobile mirror, screenshot, WOL, auth
task_executor.py         — Autonomous agent engine, JSON planner, step execution
clap_listener.py         — Double-clap detection via RMS/spike analysis
screen_watcher.py        — Background screen capture, Gemini Vision reactions
notification_listener.py — Windows notification DB polling and reader
reminder_engine.py       — Timers, reminders, daily briefing
spotify_helper.py        — Spotify URI control and API search
settings.py              — Settings manager, PROTECTED_KEYS, AppData migration
updater.py               — GitHub Releases auto-updater
notes.py                 — JSON note system
sfx.py                   — Windows Beep sound effects
index.html               — Desktop cyberpunk UI
mobile.html              — Mobile companion UI
call_mode.html           — Floating call mode window
startup.vbs              — Headless Windows startup launcher
version.txt              — Current version number (read by auto-updater)
```

---

## ⚠️ Security Warning

JARVIS can:
- Read your screen
- Listen via your microphone
- Read system notifications
- Control apps and windows
- Execute shell commands autonomously
- Send and receive data over your local network

**Only run this on a computer you own and trust.**

---

## 🚀 Installation

### Option A — Installer (recommended, no Python needed)

1. Download `JARVIS_Setup.exe` from the output folder
2. Run it and follow the wizard — pick your install folder, optionally add a desktop shortcut and Windows startup
3. Launch JARVIS and go to **Settings** to enter your API keys
4. Done — JARVIS will auto-update itself from GitHub on every launch

All settings and API keys are stored in `%APPDATA%\JARVIS\` and survive every update and reinstall.

---

### Option B — Run from source

#### Requirements
- Windows 11
- Python 3.11

#### 1. Clone the repo
```bash
git clone https://github.com/ArtinSHF/Jarvis-AI-Assistant.git
cd jarvis
```

#### 2. Install dependencies
```bash
py -3.11 -m pip install -r requirements.txt
```

If `pyaudio` fails on Windows:
```bash
pip install pipwin
pipwin install pyaudio
```

#### 3. Configure your API keys
Copy the example settings file:
```bash
copy jarvis_settings.example.json jarvis_settings.json
```

Then edit `jarvis_settings.json` and add:
- `gemini_api_key` — [Google AI Studio](https://aistudio.google.com)
- `spotify_client_id` / `spotify_client_secret` — [Spotify Developer Dashboard](https://developer.spotify.com)
- `steam_api_key` / `steam_user_id` — [Steam API Key](https://steamcommunity.com/dev/apikey)

#### 4. Run
```bash
py -3.11 jarvis.py
```

#### 5. (Optional) Auto-startup
Run `SETUP_STARTUP.bat` once to install the headless startup launcher. JARVIS will boot silently with Windows and wait for a double-clap or phone connection.

---

## 📱 Mobile Mirror Setup

1. Make sure your phone and PC are on the same Wi-Fi, or connect both to [Tailscale](https://tailscale.com)
2. Start JARVIS on the PC
3. Open a browser on your phone and go to:
   ```
   http://YOUR-PC-IP:5000
   ```
4. The mobile UI will connect automatically

> Make sure Windows Firewall is not blocking port 5000.

---

## 🔑 API Keys Needed

| Key | Where to get it | Required? |
|-----|----------------|-----------|
| Gemini API key | [aistudio.google.com](https://aistudio.google.com) | ✅ Yes |
| Spotify Client ID + Secret | [developer.spotify.com](https://developer.spotify.com) | Optional |
| Steam API key + User ID | [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey) | Optional |

---

## 🔄 Auto-Updates

JARVIS checks GitHub Releases on every launch. If a newer version is available it downloads just the code (~50–100KB), installs it silently in the background, and restarts. No reinstall, no manual steps.

API keys and all settings are stored in `%APPDATA%\JARVIS\` and are never touched by updates.

---

## 🔧 Troubleshooting

**Voice not working** — check microphone permissions in Windows settings, check `pyaudio` is installed correctly

**TTS not working** — check `edge-tts` and `pygame` are installed, check your audio output device

**Mobile mirror not connecting** — check firewall rules for port 5000, check both devices are on the same network or Tailscale, try opening the server URL in the phone browser directly

**JARVIS not starting** — run `debug_launch.bat` to see the full error output. Check `%APPDATA%\JARVIS\jarvis.log` for crash details

**Auto-updater not working** — check `%APPDATA%\JARVIS\updater.log` to see exactly what the updater did and where it stopped

**Notifications not appearing** — check the notification whitelist in settings includes your app names, check that `notif_enabled` is `true`

---

## 📌 Project Status

Actively developed. Core features are stable. Distributed as a standalone Windows installer with automatic updates via GitHub Releases.

---

## ❤️ Credits

Built by **Artin** — a solo personal project for learning, experimentation, and portfolio showcasing.

If something is broken or you want to ask something, open an issue.
