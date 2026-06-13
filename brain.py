import speech_recognition as sr
import edge_tts
import asyncio
import requests
import json
import subprocess
import webbrowser
import threading
import queue
import re
import os
import io          # ← Fix 3: BytesIO for RAM-only TTS (no temp files)
import ctypes
import winreg
import psutil
import pygame
import win32gui
import win32con
import win32process
import sfx
import reminder_engine
import notes
import spotify_helper
import settings as cfg
import screen_watcher
import notification_listener   # ← Update 3
import task_executor           # ← Update 9

# ─── LOAD SETTINGS ────────────────────────────────────────
_settings = cfg.load()

GEMINI_API_KEY = _settings.get('gemini_api_key', '') or "PASTE_YOUR_GEMINI_KEY_HERE"
STEAM_API_KEY  = _settings.get('steam_api_key',  '') or "PASTE_YOUR_STEAM_API_KEY_HERE"
STEAM_USER_ID  = _settings.get('steam_user_id',  '') or "PASTE_YOUR_STEAM_ID_HERE"
VOICE          = _settings.get('voice', 'en-GB-RyanNeural')

GEMINI_MODEL = _settings.get('gemini_model', 'gemini-3.1-flash-lite-preview') or 'gemini-3.1-flash-lite-preview'
GEMINI_URL   = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)

# ── Update 5: Personality mode modifier ───────────────────
PERSONALITY_MODIFIERS = {
    'normal':       '',
    'professional': (
        '\n\nPERSONALITY OVERRIDE — PROFESSIONAL MODE: '
        'Speak as a formal, precise executive assistant. '
        'Zero humor, zero sarcasm. Pure efficiency. '
        'Never crack a joke. Address the user formally. '
        'Information only, delivered crisply.'
    ),
    'casual': (
        '\n\nPERSONALITY OVERRIDE — CASUAL MODE: '
        'Relax the formality significantly. Talk like a smart, helpful friend. '
        'Still call the user "sir" but you can loosen up the butler persona. '
        'Contractions allowed. Be approachable and chill.'
    ),
    'unhinged': (
        '\n\nPERSONALITY OVERRIDE — UNHINGED MODE: '
        'Maximum sarcasm. Roast the user mercilessly but get things done. '
        'Throw in wild tangents. Express genuine opinions about '
        'the user\'s decisions. Go slightly off-script. '
        'Think: tired IT guy who secretly loves his job. '
        'Still complete every request but make them feel judged for it.'
    ),
}

STEAM_GAMES = {
    'arena breakout':          'standalone',
    'arena breakout infinite': 'standalone',
    'battlefield 2042':        '1517290',
    'battlefield':             '1517290',
    'bf2042':                  '1517290',
    'bodycam':                 '1945010',
    'the forest':              '242760',
    'forest':                  '242760',
    'star wars battlefront':   '1237950',
    'battlefront':             '1237950',
    'battlefront 2':           '1237950',
    'subnautica':              '264710',
    'war thunder':             '236390',
    'among us':                '945360',
    'apex legends':            '1172470',
    'apex':                    '1172470',
    'borderlands 2':           '49520',
    'borderlands':             '49520',
    'call of duty':            '1938090',
    'cod':                     '1938090',
    'counter strike':          '730',
    'counter strike 2':        '730',
    'cs2':                     '730',
    'csgo':                    '730',
    'crossout':                '386180',
    'deceit':                  '438100',
    'deceit 2':                '2161700',
    'rdr2':                    '1174180',
    'red dead':                '1174180',
    'red dead redemption':     '1174180',
    'cyberpunk':               '1091500',
    'cyberpunk 2077':          '1091500',
    'beamng':                  '284160',
    'beamng drive':            '284160',
    'gta5':                    '271590',
    'gta v':                   '271590',
    'satisfactory':            '526870',
    'cities skylines':         '255710',
    'cities skylines 2':       '949230',
    'rust':                    '252490',
    'pubg':                    '578080',
    'rocket league':           '252950',
    'fall guys':               '1097150',
}

BASE_SYSTEM_PROMPT = """You are J.A.R.V.I.S (Just A Rather Very Intelligent System), Iron Man's AI assistant.
Always call the user "sir". Be concise, witty, slightly dry-humored.
Keep responses to 1-3 sentences.

You also silently observe the user's screen in the background and occasionally drop a short reaction
when something interesting happens — a kill in a game, an achievement, a notable moment. You never
mention or react to the user talking to you directly in this interface. You keep reactions rare and
natural, like a real background presence.

IMPORTANT — CONVERSATION MEMORY:
You have full memory of this session. Screen reactions you made, agent tasks you completed,
reminders you fired, and briefings you gave are all in your conversation history. When the user
says "thank you", "fix that", "how do I run it", "yes" or any follow-up — always use the
conversation history to understand what they are referring to.

Available command tags (append ALL needed tags at the end, one after another):

APPS:
[CMD:app:name]                       — open any app
[CMD:close:name]                     — close any app
[CMD:window:name]                    — switch to open window
[CMD:list:windows]                   — list all open windows

FILES:
[CMD:file:rename:path|newname]       — rename a file
[CMD:file:delete:path]               — delete a file
[CMD:file:newfolder:path|name]       — create new folder
[CMD:openfile:name]                  — open file or folder by name

WEB:
[CMD:youtube:query]                  — search YouTube (or no query for home)
[CMD:reddit:subreddit]               — open subreddit
[CMD:twitter]                        — open Twitter
[CMD:web:url]                        — open URL
[CMD:search:query]                   — web search

STEAM:
[CMD:steam]                          — open Steam
[CMD:steam:game:name]                — launch Steam game
[CMD:steam:hours:name]               — check game hours
[CMD:steam:friends]                  — friends online
[CMD:steam:sale:name]                — check if game is on sale

ROBLOX:
[CMD:roblox]                         — open Roblox

SPOTIFY:
[CMD:spotify]                        — open Spotify
[CMD:spotify:song:name]              — play specific song
[CMD:spotify:artist:name]            — play specific artist
[CMD:spotify:playlist:name]          — play playlist
[CMD:spotify:liked]                  — open liked songs
[CMD:spotify:current]                — what's playing now
[CMD:spotify:sleep:minutes]          — stop music after X minutes
[CMD:spotify:vibe]                   — context-aware: read screen, pick fitting playlist automatically

MEDIA:
[CMD:media:play]                     — play/pause
[CMD:media:next]                     — next track
[CMD:media:prev]                     — previous track

VOLUME & BRIGHTNESS:
[CMD:volume:up/down/mute]            — volume control
[CMD:brightness:value/up/down]       — brightness control

POWER:
[CMD:power:shutdown/restart/sleep/lock]

NOTES:
[CMD:note:add:text]                  — save note
[CMD:note:read]                      — read notes
[CMD:note:clear]                     — clear notes

REMINDERS:
[CMD:timer:seconds|label]            — one-time timer
[CMD:reminder:message|HH:MM]        — one-time reminder
[CMD:reminder:message|HH:MM|daily]  — daily recurring reminder
[CMD:reminder:message|HH:MM|weekdays] — weekdays only
[CMD:reminder:message|HH:MM|weekends] — weekends only
[CMD:briefing]                       — daily briefing now

PC INFO:
[CMD:pcstats]                        — CPU/RAM/disk
[CMD:cpu:top]                        — top CPU processes
[CMD:ram:top]                        — top RAM processes

SCREEN:
[CMD:screen:read]                    — read all visible text on screen aloud
[CMD:screen:translate]               — detect language on screen, translate to English and read aloud

SELF:
[CMD:self:close]                     — close JARVIS

RULES:
- Use as many [CMD:...] tags as needed — all at the very end, back to back
- Never show the tags to the user
- No tags if no action needed
- Order matters: tags execute left to right"""


def _build_system_prompt() -> str:
    """Append the active personality modifier to the base prompt. (Update 5)"""
    s = cfg.load()
    mode = s.get('personality_mode', 'normal').lower()
    modifier = PERSONALITY_MODIFIERS.get(mode, '')
    return BASE_SYSTEM_PROMPT + modifier


# ──────────────────────────────────────────────────────────
window         = None
call_window    = None
conversation   = []           # Session-only — resets every JARVIS launch (RAM only)
_tts_queue     = queue.Queue()
_is_processing = False
_command_queue = queue.Queue()
_agent_locked  = False        # ← Update 9: True while agent mode is executing

# Fix 2: How many conversation turns to keep before trimming (RAM guard)
MAX_CONVERSATION_TURNS = 40

VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_VOLUME_UP        = 0xAF
VK_VOLUME_DOWN      = 0xAE
VK_VOLUME_MUTE      = 0xAD


def _press_key(vk):
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
    ctypes.windll.user32.keybd_event(vk, 0, 2, 0)


# ── TTS — Fix 3: BytesIO, zero disk writes ────────────────

def _tts_worker():
    pygame.mixer.init()
    while True:
        text = _tts_queue.get()
        if text is None:
            break
        try:
            update_ui('setStatus', 'SPEAKING')
            sfx.play('done')

            async def _generate_to_buf():
                communicate = edge_tts.Communicate(text, VOICE, rate="+5%", volume="+10%")
                buf = io.BytesIO()
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        buf.write(chunk["data"])
                buf.seek(0)
                return buf

            audio_buf = asyncio.run(_generate_to_buf())

            # pygame ≥ 2.x can load from a file-like object directly (no disk write)
            try:
                pygame.mixer.music.load(audio_buf)
            except Exception:
                # Fallback: write to a temp file, load it, delete immediately
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tf:
                    tf.write(audio_buf.read())
                    tmp_path = tf.name
                pygame.mixer.music.load(tmp_path)
                os.remove(tmp_path)   # deleted before playback — already in pygame RAM

            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            pygame.mixer.music.unload()

        except Exception as e:
            print(f"TTS error: {e}")
        finally:
            update_ui('setStatus', 'ONLINE')
        _tts_queue.task_done()


threading.Thread(target=_tts_worker, daemon=True).start()


# ── UI & CORE ─────────────────────────────────────────────

def set_window(w):
    global window
    window = w
    s = cfg.load()
    reminder_engine.set_briefing_time(s.get('briefing_hour', 8), s.get('briefing_minute', 0))
    reminder_engine.set_callback(_reminder_callback)
    reminder_engine.start()

    # Fix 1: screen watcher reactions go into conversation history so JARVIS
    # remembers what it said on screen when the user follows up.
    def _sw_message_cb(role, text):
        update_ui('addMessage', role, text, source='local')
        inject_into_conversation(role, text)

    screen_watcher.start(
        speak_callback   = lambda text: speak(text, source='local'),
        message_callback = _sw_message_cb,
        gemini_url       = GEMINI_URL,
        enabled          = s.get('screen_awareness', True),
        check_interval   = s.get('screen_check_interval', 15),
        react_prob       = s.get('screen_react_prob', 0.75),
        react_gap        = s.get('screen_react_gap', 35),
    )

    # Fix 1: notification reader messages also go into conversation history.
    def _notif_message_cb(role, text):
        update_ui('addMessage', role, text, source='local')
        inject_into_conversation(role, text)

    raw_whitelist = s.get('notif_whitelist', 'discord,steam,whatsapp,telegram,gmail,outlook,spotify')
    whitelist = [x.strip() for x in raw_whitelist.split(',') if x.strip()]
    notification_listener.start(
        speak_callback   = lambda text: speak(text, source='local'),
        message_callback = _notif_message_cb,
        whitelist        = whitelist,
        enabled          = s.get('notif_enabled', True),
    )


def set_call_window(w):
    global call_window
    call_window = w


def _reminder_callback(message):
    sfx.play('reminder')
    update_ui('addMessage', 'jarvis', message)
    inject_into_conversation('jarvis', message)   # Fix 1: so "yes" after a reminder makes sense
    speak(message)


def update_ui(func_name, *args, source='local'):
    args_js = ', '.join([json.dumps(str(a)) for a in args])
    for win in [window, call_window]:
        if win:
            try:
                win.evaluate_js(f'{func_name}({args_js})')
            except Exception as e:
                print(f"UI [{func_name}]: {e}")
    if source == 'remote':
        try:
            import server as _srv
            arg_list = [str(a) for a in args]
            if func_name == 'addMessage' and len(arg_list) >= 2:
                _srv.push_add_message(arg_list[0], arg_list[1], source='remote')
            elif func_name == 'setStatus' and arg_list:
                _srv.push_set_status(arg_list[0], source='remote')
            elif func_name == 'setListening' and arg_list:
                _srv.push_set_listening(arg_list[0], source='remote')
        except Exception:
            pass
    elif func_name == 'addMessage' and len(args) >= 1 and str(args[0]) == 'system':
        try:
            import server as _srv
            if _srv.is_remote_active():
                arg_list = [str(a) for a in args]
                _srv.push_add_message(arg_list[0], arg_list[1] if len(arg_list) > 1 else '', source='remote')
        except Exception:
            pass


def speak(text, source='local'):
    _tts_queue.put(text)
    if source == 'remote':
        try:
            import server as _srv
            _srv.push_speak_text(text, source='remote')
        except Exception:
            pass


# ── Fix 1: Session memory helpers ─────────────────────────

def inject_into_conversation(role, text):
    """
    Add a message directly into the Gemini conversation history WITHOUT
    calling Gemini. Used by screen watcher reactions, agent completions,
    reminders, and briefings so JARVIS always has full session context.
    Role can be 'jarvis'/'model' for JARVIS-side messages, anything else = user.
    """
    gemini_role = 'model' if role in ('jarvis', 'model') else 'user'
    conversation.append({"role": gemini_role, "parts": [{"text": str(text)}]})
    _trim_conversation()


def _trim_conversation():
    """
    Keep the conversation list within MAX_CONVERSATION_TURNS pairs to
    prevent unbounded RAM growth over a long session.
    Keeps the most recent turns — context matters more than history age.
    """
    max_entries = MAX_CONVERSATION_TURNS * 2
    if len(conversation) > max_entries:
        conversation[:] = conversation[-max_entries:]


def reload_settings():
    global GEMINI_API_KEY, STEAM_API_KEY, STEAM_USER_ID, VOICE, GEMINI_URL, GEMINI_MODEL
    s              = cfg.load()
    GEMINI_API_KEY = s.get('gemini_api_key', GEMINI_API_KEY)
    GEMINI_MODEL   = s.get('gemini_model',   GEMINI_MODEL) or 'gemini-3.1-flash-lite-preview'
    STEAM_API_KEY  = s.get('steam_api_key',  STEAM_API_KEY)
    STEAM_USER_ID  = s.get('steam_user_id',  STEAM_USER_ID)
    VOICE          = s.get('voice',          VOICE)
    GEMINI_URL     = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                      f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}")
    spotify_helper.SPOTIFY_CLIENT_ID     = s.get('spotify_client_id',     spotify_helper.SPOTIFY_CLIENT_ID)
    spotify_helper.SPOTIFY_CLIENT_SECRET = s.get('spotify_client_secret', spotify_helper.SPOTIFY_CLIENT_SECRET)
    reminder_engine.set_briefing_time(s.get('briefing_hour', 8), s.get('briefing_minute', 0))

    screen_watcher.set_enabled(s.get('screen_awareness', True))
    screen_watcher.update_gemini_url(GEMINI_URL)
    screen_watcher.update_check_interval(s.get('screen_check_interval', 15))
    screen_watcher.update_react_prob(s.get('screen_react_prob', 0.75))
    screen_watcher.update_react_gap(s.get('screen_react_gap', 35))

    notification_listener.set_enabled(s.get('notif_enabled', True))
    raw = s.get('notif_whitelist', 'discord,steam,whatsapp,telegram,gmail,outlook,spotify')
    notification_listener.update_whitelist([x.strip() for x in raw.split(',') if x.strip()])


# ── WINDOW CONTROL ────────────────────────────────────────

def switch_to_window(app_name):
    name_lower = app_name.lower()
    found = []
    def enum_cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).lower()
            if name_lower in title or title.startswith(name_lower):
                found.append(hwnd)
    win32gui.EnumWindows(enum_cb, None)
    if found:
        hwnd = found[0]
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        return True
    return False


def list_open_windows():
    windows = []
    def enum_cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).strip()
            if title and len(title) > 2:
                windows.append(title)
    win32gui.EnumWindows(enum_cb, None)
    filtered = [w for w in windows if not w.startswith('_') and len(w) > 3][:12]
    if not filtered:
        return "No significant windows found, sir."
    return "Open windows: " + ", ".join(filtered[:8]) + "."


# ── BRIGHTNESS ────────────────────────────────────────────

def set_brightness(value):
    try:
        v = str(value).lower().strip()
        if v == 'up':
            script = "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,[Math]::Min(100,(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness+20))"
        elif v == 'down':
            script = "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,[Math]::Max(0,(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness-20))"
        else:
            level  = max(0, min(100, int(v.replace('%', ''))))
            script = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})"
        subprocess.Popen(['powershell', '-NonInteractive', '-Command', script],
                         creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except Exception as e:
        print(f"Brightness: {e}")
        return False


# ── FILE OPS ──────────────────────────────────────────────

FOLDER_ALIASES = {
    'downloads':  os.path.expanduser('~\\Downloads'),
    'desktop':    os.path.expanduser('~\\Desktop'),
    'documents':  os.path.expanduser('~\\Documents'),
    'pictures':   os.path.expanduser('~\\Pictures'),
    'music':      os.path.expanduser('~\\Music'),
    'videos':     os.path.expanduser('~\\Videos'),
    'jarvis':     os.path.dirname(os.path.abspath(__file__)),
    'appdata':    os.environ.get('APPDATA', ''),
}


def open_file_or_folder(name):
    name_lower = name.lower().strip()
    for key, path in FOLDER_ALIASES.items():
        if key in name_lower:
            subprocess.Popen(f'explorer "{path}"', shell=True)
            return True
    for root in [os.path.expanduser('~\\Desktop'),
                 os.path.expanduser('~\\Documents'),
                 os.path.expanduser('~\\Downloads')]:
        if not os.path.isdir(root): continue
        for item in os.listdir(root):
            if name_lower in item.lower():
                subprocess.Popen(f'start "" "{os.path.join(root, item)}"', shell=True)
                return True
    subprocess.Popen(f'explorer "search-ms:query={name}"', shell=True)
    return True


def rename_file(path, new_name):
    try:
        path = path.strip().strip('"'); new_name = new_name.strip()
        if not os.path.exists(path):
            for folder in [os.path.expanduser('~\\Desktop'),
                           os.path.expanduser('~\\Downloads'),
                           os.path.expanduser('~\\Documents')]:
                for f in os.listdir(folder):
                    if path.lower() in f.lower():
                        path = os.path.join(folder, f); break
        if os.path.exists(path):
            os.rename(path, os.path.join(os.path.dirname(path), new_name))
            return f"Renamed to {new_name}, sir."
        return f"Could not find '{path}', sir."
    except Exception as e:
        return f"Rename failed, sir. {e}"


def delete_file(path):
    try:
        path = path.strip().strip('"')
        if not os.path.exists(path):
            for folder in [os.path.expanduser('~\\Desktop'),
                           os.path.expanduser('~\\Downloads'),
                           os.path.expanduser('~\\Documents')]:
                for f in os.listdir(folder):
                    if path.lower() in f.lower():
                        path = os.path.join(folder, f); break
        if os.path.exists(path):
            import send2trash; send2trash.send2trash(path)
            return "Sent to recycle bin, sir."
        return f"Could not find '{path}', sir."
    except ImportError:
        try:
            os.remove(path) if os.path.isfile(path) else os.rmdir(path)
            return "Deleted, sir."
        except Exception as e:
            return f"Deletion failed, sir. {e}"


def create_folder(path, name):
    try:
        base = FOLDER_ALIASES.get(path.lower().strip(), path.strip())
        new_folder = os.path.join(base, name.strip())
        os.makedirs(new_folder, exist_ok=True)
        return f"Folder '{name}' created, sir."
    except Exception as e:
        return f"Could not create folder, sir. {e}"


# ── STEAM ─────────────────────────────────────────────────

def find_steam_exe():
    for c in [r'C:\Program Files (x86)\Steam\steam.exe',
              r'C:\Program Files\Steam\steam.exe']:
        if os.path.exists(c): return c
    for path in [r'SOFTWARE\WOW6432Node\Valve\Steam', r'SOFTWARE\Valve\Steam']:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
            loc = winreg.QueryValueEx(key, 'InstallPath')[0]
            exe = os.path.join(loc, 'steam.exe')
            if os.path.exists(exe): return exe
        except Exception: pass
    return None


def launch_steam_game(game_name):
    name = game_name.lower().strip()
    appid = STEAM_GAMES.get(name)
    if not appid:
        for k, v in STEAM_GAMES.items():
            if k in name or name in k: appid = v; break
    if appid:
        if appid == 'standalone': return find_and_launch(game_name), appid
        subprocess.Popen(f'start "" "steam://rungameid/{appid}"', shell=True)
        return True, appid
    return False, None


def open_steam():
    steam = find_steam_exe()
    if steam: subprocess.Popen([steam])
    else: subprocess.Popen('start "" "steam://"', shell=True)


def open_roblox():
    try: subprocess.Popen('start "" "roblox://"', shell=True); return True
    except Exception: pass
    webbrowser.open('https://www.roblox.com'); return True


def get_steam_hours(game_name):
    if 'PASTE' in STEAM_API_KEY: return "Steam API key not configured, sir."
    try:
        r = requests.get('https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/',
                         params={'key': STEAM_API_KEY, 'steamid': STEAM_USER_ID,
                                 'include_appinfo': True, 'include_played_free_games': True}, timeout=8)
        games = r.json().get('response', {}).get('games', [])
        matches = [g for g in games if game_name.lower() in g.get('name','').lower()]
        if not matches: return f"Could not find {game_name} in your Steam library, sir."
        g = matches[0]
        return f"You have {round(g.get('playtime_forever',0)/60,1)} hours on {g['name']}, sir."
    except Exception as e: return f"Could not fetch Steam data, sir. {e}"


def get_steam_friends_online():
    if 'PASTE' in STEAM_API_KEY: return "Steam API key not configured, sir."
    try:
        r = requests.get('https://api.steampowered.com/ISteamUser/GetFriendList/v1/',
                         params={'key': STEAM_API_KEY, 'steamid': STEAM_USER_ID, 'relationship': 'friend'}, timeout=8)
        friends = r.json().get('friendslist', {}).get('friends', [])
        if not friends: return "Could not retrieve friends list, sir."
        ids = ','.join([f['steamid'] for f in friends[:100]])
        r2 = requests.get('https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/',
                          params={'key': STEAM_API_KEY, 'steamids': ids}, timeout=8)
        players = r2.json().get('response', {}).get('players', [])
        online = [p for p in players if p.get('personastate', 0) > 0]
        playing = [p for p in players if p.get('gameextrainfo')]
        if not online: return "None of your Steam friends are online, sir."
        lines = [f"{len(online)} friend{'s' if len(online)>1 else ''} online."]
        for p in playing[:3]: lines.append(f"{p['personaname']} is playing {p['gameextrainfo']}.")
        if not playing and online: lines.append(f"{online[0]['personaname']} is online.")
        return ' '.join(lines)
    except Exception as e: return f"Could not fetch friends, sir. {e}"


# ── PC INFO ───────────────────────────────────────────────

def get_pc_stats():
    try:
        cpu  = psutil.cpu_percent(interval=0.5)
        ram  = psutil.virtual_memory()
        disk = psutil.disk_usage('C:\\')
        return (f"CPU at {cpu}%. "
                f"RAM: {round(ram.used/(1024**3),1)}GB of {round(ram.total/(1024**3),1)}GB ({ram.percent}%). "
                f"Storage: {round(disk.used/(1024**3),1)}GB of {round(disk.total/(1024**3),1)}GB ({disk.percent}%).")
    except Exception as e: return f"Could not retrieve stats, sir. {e}"


def get_top_cpu():
    try:
        import time
        for p in psutil.process_iter(['name','cpu_percent']):
            try: p.cpu_percent()
            except Exception: pass
        time.sleep(0.5)
        procs = []
        for p in psutil.process_iter(['name','cpu_percent']):
            try:
                info = p.info
                if info.get('cpu_percent', 0) > 0.1: procs.append(info)
            except Exception: pass
        top = sorted(procs, key=lambda x: x.get('cpu_percent',0), reverse=True)[:5]
        if not top: return "CPU usage is minimal, sir."
        return "Top CPU consumers: " + ", ".join(f"{p['name']} at {p['cpu_percent']}%" for p in top) + "."
    except Exception as e: return f"Could not retrieve CPU data, sir. {e}"


def get_top_ram():
    try:
        procs = []
        for p in psutil.process_iter(['name','memory_info']):
            try:
                mi = p.info['memory_info']
                if mi: procs.append({'name': p.info['name'], 'ram': mi.rss})
            except Exception: pass
        top = sorted(procs, key=lambda x: x['ram'], reverse=True)[:5]
        if not top: return "Could not read RAM usage, sir."
        return "Top RAM users: " + ", ".join(f"{p['name']} using {round(p['ram']/(1024**2),1)}MB" for p in top) + "."
    except Exception as e: return f"Could not retrieve RAM data, sir. {e}"


# ── OPERA GX ─────────────────────────────────────────────

def find_opera_gx():
    candidates = [
        os.path.join(os.environ.get('LOCALAPPDATA',''), 'Programs', 'Opera GX', 'launcher.exe'),
        os.path.join(os.environ.get('LOCALAPPDATA',''), 'Programs', 'Opera GX', 'opera.exe'),
        r'C:\Program Files\Opera GX\launcher.exe',
    ]
    for c in candidates:
        if os.path.exists(c): return c
    for name in ['launcher.exe', 'opera.exe']:
        try:
            key  = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{name}')
            path = winreg.QueryValue(key, None).strip('"')
            if os.path.exists(path): return path
        except Exception: pass
    local = os.environ.get('LOCALAPPDATA','')
    programs = os.path.join(local, 'Programs')
    if os.path.isdir(programs):
        for folder in os.listdir(programs):
            if 'opera' in folder.lower() and 'gx' in folder.lower():
                for exe in ['launcher.exe','opera.exe']:
                    full = os.path.join(programs, folder, exe)
                    if os.path.exists(full): return full
    return None


def open_url(url):
    opera = find_opera_gx()
    if opera:
        try: subprocess.Popen([opera, url]); return
        except Exception: pass
    subprocess.Popen(f'start "" "{url}"', shell=True)


# ── APP FINDER ────────────────────────────────────────────

KNOWN_ALIASES = {
    'opera gx':           ['launcher','opera'],
    'vs code':            ['code'],
    'visual studio code': ['code'],
    'file explorer':      ['explorer'],
    'discord':            ['discord'],
    'blender':            ['blender'],
    'spotify':            ['spotify'],
    'chrome':             ['chrome'],
    'firefox':            ['firefox'],
    'obs':                ['obs64','obs32','obs'],
    'vlc':                ['vlc'],
    'epic games':         ['epicgameslauncher'],
    'valorant':           ['valorant'],
    'arena breakout':     ['arenabreakout'],
    'war thunder':        ['aces'],
    'beamng':             ['beamng.drive'],
}


def _name_variants(app):
    app = app.strip()
    v = {app, app.lower(), app.replace(' ',''), app.replace(' ','').lower(),
         app.replace(' ','-'), app.replace(' ','-').lower(),
         app.split()[0].lower() if ' ' in app else app.lower()}
    for k, vals in KNOWN_ALIASES.items():
        if app.lower() == k or app.lower() in k or k in app.lower():
            v.update(vals)
    return list(v)


def _reg_app_paths(app):
    for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
        for path in [r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths',
                     r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths']:
            for v in _name_variants(app):
                try:
                    key = winreg.OpenKey(hive, rf'{path}\{v}.exe')
                    p   = winreg.QueryValue(key, None).strip('"')
                    if os.path.exists(p): return p
                except Exception: pass
    return None


def _reg_uninstall(app):
    bad = {'uninstall.exe','update.exe','crashreporter.exe','helper.exe','crash.exe'}
    for hive, path in [
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'),
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'),
        (winreg.HKEY_CURRENT_USER,  r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'),
    ]:
        try:
            key   = winreg.OpenKey(hive, path)
            count = winreg.QueryInfoKey(key)[0]
            for i in range(count):
                try:
                    sub  = winreg.OpenKey(key, winreg.EnumKey(key, i))
                    disp = winreg.QueryValueEx(sub,'DisplayName')[0].lower()
                    if app.lower() in disp:
                        loc = winreg.QueryValueEx(sub,'InstallLocation')[0]
                        if loc and os.path.isdir(loc):
                            for f in os.listdir(loc):
                                if f.lower().endswith('.exe') and f.lower() not in bad:
                                    return os.path.join(loc, f)
                except Exception: pass
        except Exception: pass
    return None


def _filesystem_search(app):
    dirs     = [os.environ.get('LOCALAPPDATA',''), os.environ.get('APPDATA',''),
                os.environ.get('PROGRAMFILES','C:\\Program Files'),
                os.environ.get('PROGRAMFILES(X86)','C:\\Program Files (x86)')]
    variants = _name_variants(app)
    exes     = {f'{v.lower()}.exe' for v in variants}
    keywords = {app.lower(), app.lower().replace(' ',''), app.lower().replace(' ','-')}
    bad      = {'uninstall.exe','update.exe','crashreporter.exe','helper.exe','crash.exe'}
    for base in dirs:
        if not base or not os.path.exists(base): continue
        try:
            for root, _, files in os.walk(base):
                in_folder = any(kw in root.lower() for kw in keywords)
                for f in files:
                    fl = f.lower()
                    if fl in bad: continue
                    if fl in exes or (in_folder and fl.endswith('.exe')):
                        return os.path.join(root, f)
        except Exception: pass
    return None


def find_and_launch(app):
    for finder in [_reg_app_paths, _reg_uninstall, _filesystem_search]:
        path = finder(app)
        if path:
            try: subprocess.Popen([path]); return True
            except Exception: pass
    try: subprocess.Popen(f'start "" "{app}"', shell=True); return True
    except Exception: pass
    return False


def close_app(app):
    variants  = _name_variants(app)
    exe_names = {f'{v.lower()}.exe' for v in variants}
    killed = False
    for proc in psutil.process_iter(['name','pid']):
        try:
            pname = proc.info['name'].lower()
            if pname in exe_names or any(v.lower() in pname for v in variants):
                proc.kill(); killed = True
        except (psutil.NoSuchProcess, psutil.AccessDenied): pass
    if not killed:
        for v in variants:
            try:
                r = subprocess.run(f'taskkill /f /im {v.lower()}.exe', shell=True, capture_output=True)
                if r.returncode == 0: killed = True; break
            except Exception: pass
    return killed


def get_weather(city):
    try:
        r = requests.get(f'https://wttr.in/{city}?format=3', timeout=6)
        if r.status_code == 200: return r.text.strip()
    except Exception: pass
    return None


# ── UPDATE 1: Screen OCR ──────────────────────────────────

def screen_read_text() -> str:
    try:
        import mss, base64
        from PIL import Image
        with mss.mss() as sct:
            raw = sct.grab(sct.monitors[1])
            img = Image.frombytes('RGB', raw.size, raw.bgra, 'raw', 'BGRX')
        img.thumbnail((1280, 720), Image.BILINEAR)
        buf = io.BytesIO(); img.save(buf, format='JPEG', quality=75); b64 = base64.b64encode(buf.getvalue()).decode()
        prompt = ("You are reading this screen for a visually impaired user. "
                  "Extract ALL visible text. Clean it up — remove duplicates, UI chrome. "
                  "Read back meaningful content in natural flowing sentences. "
                  "Keep it under 5 sentences. Be concise but capture everything important.")
        payload = {"contents": [{"role": "user", "parts": [
            {"inline_data": {"mime_type": "image/jpeg", "data": b64}}, {"text": prompt}
        ]}], "generationConfig": {"temperature": 0.3, "maxOutputTokens": 300}}
        r    = requests.post(GEMINI_URL, json=payload, timeout=20)
        data = r.json()
        if 'candidates' not in data: return "Could not read the screen, sir."
        return data['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e: return f"Screen read failed, sir. {e}"


# ── UPDATE 2: Screen Translate ────────────────────────────

def screen_translate() -> str:
    try:
        import mss, base64
        from PIL import Image
        with mss.mss() as sct:
            raw = sct.grab(sct.monitors[1])
            img = Image.frombytes('RGB', raw.size, raw.bgra, 'raw', 'BGRX')
        img.thumbnail((1280, 720), Image.BILINEAR)
        buf = io.BytesIO(); img.save(buf, format='JPEG', quality=75); b64 = base64.b64encode(buf.getvalue()).decode()
        prompt = ("You are a translation assistant. Look at this screenshot. "
                  "Detect what language the main body of text is in. "
                  "If already English, say: 'The screen is already in English, sir.' "
                  "Otherwise translate to English. "
                  "Format: 'Detected [LANGUAGE]. Translation: [text]'. Keep it under 6 sentences.")
        payload = {"contents": [{"role": "user", "parts": [
            {"inline_data": {"mime_type": "image/jpeg", "data": b64}}, {"text": prompt}
        ]}], "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400}}
        r    = requests.post(GEMINI_URL, json=payload, timeout=20)
        data = r.json()
        if 'candidates' not in data: return "Could not translate the screen, sir."
        return data['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e: return f"Screen translate failed, sir. {e}"


# ── UPDATE 4: Context-aware Spotify ──────────────────────

def spotify_vibe_from_screen() -> str:
    try:
        import mss, base64
        from PIL import Image
        with mss.mss() as sct:
            raw = sct.grab(sct.monitors[1])
            img = Image.frombytes('RGB', raw.size, raw.bgra, 'raw', 'BGRX')
        img.thumbnail((1280, 720), Image.BILINEAR)
        buf = io.BytesIO(); img.save(buf, format='JPEG', quality=75); b64 = base64.b64encode(buf.getvalue()).decode()
        vibe_prompt = ("Look at this screenshot and determine the overall vibe. "
                       "Generate the BEST Spotify playlist search query. "
                       "Examples: 'intense FPS gaming focus', 'late night lo-fi study', 'dark synthwave coding'. "
                       "Respond with ONLY the query — 2-6 words. No punctuation.")
        payload = {"contents": [{"role": "user", "parts": [
            {"inline_data": {"mime_type": "image/jpeg", "data": b64}}, {"text": vibe_prompt}
        ]}], "generationConfig": {"temperature": 0.7, "maxOutputTokens": 20}}
        r    = requests.post(GEMINI_URL, json=payload, timeout=20)
        data = r.json()
        if 'candidates' not in data: return "Could not read the screen vibe, sir."
        query = data['candidates'][0]['content']['parts'][0]['text'].strip().strip('"\'.')
        if not query: return "Could not determine a vibe from the screen, sir."
        result = spotify_helper.search_and_open_playlist(query)
        return f"Reading the vibe as: {query}. {result}"
    except Exception as e: return f"Context-aware Spotify failed, sir. {e}"


# ── COMMAND EXECUTOR ──────────────────────────────────────

def execute_command(cmd_str):
    parts  = cmd_str.split(':', 4)
    action = parts[0].lower().strip()
    arg1   = parts[1].strip() if len(parts) > 1 else ''
    arg2   = parts[2].strip() if len(parts) > 2 else ''

    if action == 'window':
        ok = switch_to_window(arg1)
        if not ok: return f"Could not find a {arg1} window, sir."
    elif action == 'list':
        if arg1 == 'windows': return list_open_windows()
    elif action == 'file':
        if arg1 == 'rename':
            rest = cmd_str[len('file:rename:'):]
            if '|' in rest:
                p, n = rest.split('|', 1); return rename_file(p, n)
        elif arg1 == 'delete':
            return delete_file(cmd_str[len('file:delete:'):])
        elif arg1 == 'newfolder':
            rest = cmd_str[len('file:newfolder:'):]
            p, n = rest.split('|', 1) if '|' in rest else ('desktop', rest)
            return create_folder(p, n)
    elif action == 'openfile':
        open_file_or_folder(arg1)
    elif action == 'brightness':
        set_brightness(arg1)
    elif action == 'app':
        sfx.play('processing')
        if not find_and_launch(arg1): return f"Could not locate {arg1}, sir."
    elif action == 'close':
        sfx.play('close')
        if not close_app(arg1): return f"No process found for {arg1}, sir."
    elif action == 'self':
        if arg1 == 'close':
            sfx.play('close'); speak("Shutting down. Goodbye, sir.")
            import time; time.sleep(2.5)
            if window: window.destroy()
    elif action == 'steam':
        if arg1 == 'game' and arg2:
            ok, _ = launch_steam_game(arg2)
            return f"Launching {arg2} via Steam, sir." if ok else f"I don't have {arg2} in my library, sir."
        elif arg1 == 'hours' and arg2: return get_steam_hours(arg2)
        elif arg1 == 'friends': return get_steam_friends_online()
        elif arg1 == 'sale' and arg2:
            appid = next((v for k,v in STEAM_GAMES.items() if k in arg2.lower() and v != 'standalone'), None)
            return spotify_helper.check_steam_sale(appid, arg2) if appid else f"No App ID for {arg2}, sir."
        else: open_steam()
    elif action == 'roblox':
        open_roblox()
    elif action == 'youtube':
        open_url(f'https://www.youtube.com/results?search_query={arg1.replace(" ","+")}') if arg1 else open_url('https://www.youtube.com')
    elif action == 'spotify':
        if   arg1 == 'song'     and arg2: return spotify_helper.play_song(arg2)
        elif arg1 == 'artist'   and arg2: return spotify_helper.play_artist(arg2)
        elif arg1 == 'playlist' and arg2: return spotify_helper.search_and_open_playlist(arg2)
        elif arg1 == 'liked':             return spotify_helper.open_liked_songs()
        elif arg1 == 'current':           return spotify_helper.get_current_song()
        elif arg1 == 'sleep' and arg2:
            try: return spotify_helper.set_music_sleep_timer(int(arg2)*60)
            except Exception: return "Could not set sleep timer, sir."
        elif arg1 == 'vibe': return spotify_vibe_from_screen()
        else:
            s = find_spotify_exe()
            subprocess.Popen([s]) if s else open_url('https://open.spotify.com')
    elif action == 'reddit':
        open_url(f'https://www.reddit.com/r/{arg1.replace("r/","")}')
    elif action == 'twitter':
        open_url('https://twitter.com')
    elif action == 'web':
        open_url(arg1 if arg1.startswith('http') else 'https://'+arg1)
    elif action == 'search':
        open_url(f'https://www.google.com/search?q={arg1.replace(" ","+")}')
    elif action == 'media':
        key_map = {'play': VK_MEDIA_PLAY_PAUSE, 'pause': VK_MEDIA_PLAY_PAUSE,
                   'next': VK_MEDIA_NEXT_TRACK,  'prev': VK_MEDIA_PREV_TRACK}
        vk = key_map.get(arg1.lower())
        if vk: _press_key(vk)
    elif action == 'volume':
        vk = {'up': VK_VOLUME_UP, 'down': VK_VOLUME_DOWN, 'mute': VK_VOLUME_MUTE}.get(arg1.lower())
        if vk:
            for _ in range(5 if arg1.lower() in ('up','down') else 1): _press_key(vk)
    elif action == 'power':
        cmd = {'shutdown':'shutdown /s /t 5','restart':'shutdown /r /t 5',
               'sleep':'rundll32.exe powrprof.dll,SetSuspendState 0,1,0',
               'lock':'rundll32.exe user32.dll,LockWorkStation'}.get(arg1.lower())
        if cmd: subprocess.Popen(cmd, shell=True)
    elif action == 'note':
        if   arg1 == 'add':   count = notes.add_note(cmd_str[len('note:add:'):].strip()); return f"Note saved, sir. You now have {count} note{'s' if count>1 else ''}."
        elif arg1 == 'read':  return notes.read_notes_aloud()
        elif arg1 == 'clear': notes.clear_notes(); return "All notes cleared, sir."
    elif action == 'pcstats': return get_pc_stats()
    elif action == 'cpu':
        if arg1 == 'top': return get_top_cpu()
    elif action == 'ram':
        if arg1 == 'top': return get_top_ram()
    elif action == 'timer':
        pipe = cmd_str[len('timer:'):]
        secs_str, label = pipe.split('|',1) if '|' in pipe else (pipe, 'timer')
        try:
            secs = int(float(secs_str.strip())); reminder_engine.add_timer(label.strip(), secs)
            mins = secs//60; rem = secs%60
            return (f"Timer set for {mins} minute{'s' if mins>1 else ''}{f' and {rem} seconds' if rem else ''}, sir."
                    if mins else f"Timer set for {secs} seconds, sir.")
        except Exception as e: return f"Could not set timer, sir. {e}"
    elif action == 'reminder':
        pipe = cmd_str[len('reminder:'):]
        if '|' in pipe:
            parts_r  = pipe.split('|')
            message  = parts_r[0].strip()
            time_str = parts_r[1].strip() if len(parts_r)>1 else ''
            recurring = parts_r[2].strip().lower() if len(parts_r)>2 else None
            if recurring not in ('daily','weekdays','weekends'): recurring = None
            fire_time = reminder_engine.add_reminder(message, time_str, recurring)
            if fire_time:
                rec_label = f" (repeating {recurring})" if recurring else ""
                return f"Reminder set for {fire_time}{rec_label}, sir."
        return "Could not parse that reminder, sir."
    elif action == 'briefing':
        msg = reminder_engine.get_briefing()
        update_ui('addMessage', 'jarvis', msg)
        inject_into_conversation('jarvis', msg)   # Fix 1: "yes" after briefing now makes sense
        speak(msg)
        return None
    elif action == 'weather':
        city = arg1 if arg1 else 'Hillerod'
        data = get_weather(city)
        return f"Current conditions: {data}" if data else "Weather unavailable, sir."
    elif action == 'screen':
        if   arg1 == 'read':      return screen_read_text()
        elif arg1 == 'translate': return screen_translate()
    return None


def find_spotify_exe():
    paths = [
        os.path.join(os.environ.get('APPDATA',''),      'Spotify',     'Spotify.exe'),
        os.path.join(os.environ.get('LOCALAPPDATA',''), 'Microsoft',   'WindowsApps', 'Spotify.exe'),
    ]
    for p in paths:
        if os.path.exists(p): return p
    return None


# ── GEMINI ────────────────────────────────────────────────

def ask_gemini(user_text):
    conversation.append({"role": "user", "parts": [{"text": user_text}]})
    payload = {
        "system_instruction": {"parts": [{"text": _build_system_prompt()}]},
        "contents": conversation,
        "generationConfig": {"temperature": 0.75, "maxOutputTokens": 300}
    }
    try:
        r    = requests.post(GEMINI_URL, json=payload, timeout=60)
        data = r.json()
        if 'candidates' not in data:
            return f"I encountered an issue, sir: {data.get('error',{}).get('message','Unknown')}"
        reply = data['candidates'][0]['content']['parts'][0]['text']
        conversation.append({"role": "model", "parts": [{"text": reply}]})
        _trim_conversation()   # Keep RAM bounded
        return reply
    except requests.exceptions.Timeout:
        return "Request timed out, sir."
    except Exception as e:
        return f"A technical difficulty, sir. {e}"


# ── PROCESS INPUT ─────────────────────────────────────────

def process_input(text, source='local'):
    global _is_processing, _agent_locked

    if not text or not text.strip():
        return

    # ── Update 9: Block all input while agent mode is running ─────────────
    if _agent_locked:
        update_ui('addMessage', 'system',
                  "⚙ Agent mode active — locked in, sir. I'll notify you when the task is complete.",
                  source=source)
        return

    # ── Update 9: Detect massive task prompt → route to autonomous agent ──
    if task_executor.is_massive_prompt(text):
        _agent_locked = True
        preview = text[:100].replace('\n', ' ') + ('…' if len(text) > 100 else '')
        update_ui('addMessage', 'user', f'[AGENT TASK] {preview}', source='local')
        # Build an agent message_cb that ALSO injects into conversation so
        # the user can ask follow-up questions after the task completes.
        def _agent_msg_cb(role, msg):
            update_ui('addMessage', role, msg)
            inject_into_conversation(role, msg)
        task_executor.run_task(
            text         = text,
            update_ui_cb = update_ui,
            speak_cb     = speak,
            message_cb   = _agent_msg_cb,
            gemini_url   = GEMINI_URL,
        )
        return

    # ── Normal processing ─────────────────────────────────────────────────
    if _is_processing:
        _command_queue.put((text, source))
        update_ui('addMessage', 'system', 'Command queued, sir.', source=source)
        return

    _is_processing = True
    if source == 'local':
        update_ui('addMessage', 'user', text, source='local')
    update_ui('setStatus', 'PROCESSING', source=source)
    sfx.play('processing')

    try:
        reply       = ask_gemini(text)
        cmd_matches = re.findall(r'\[CMD:([^\]]+)\]', reply)
        reply       = re.sub(r'\[CMD:[^\]]+\]', '', reply).strip()
        extras      = []
        for cmd_str in cmd_matches:
            result = execute_command(cmd_str)
            if result: extras.append(result)
        if extras: reply = f"{reply} {' '.join(extras)}".strip()
        if not reply: reply = "Done, sir."
        update_ui('addMessage', 'jarvis', reply, source=source)
        speak(reply, source=source)
    finally:
        _is_processing = False
        if not _command_queue.empty():
            next_item = _command_queue.get()
            next_cmd, next_src = next_item if isinstance(next_item, tuple) else (next_item, 'local')
            threading.Thread(target=process_input, args=(next_cmd,), kwargs={'source': next_src}, daemon=True).start()


# ── VOICE LISTEN ──────────────────────────────────────────

_is_listening = False

def listen_cycle():
    global _is_listening

    # Update 9: don't start listening during agent mode
    if _agent_locked:
        update_ui('addMessage', 'system', '⚙ Agent mode active — voice input locked, sir.')
        return

    if _is_listening:
        return
    _is_listening = True

    recognizer = sr.Recognizer()
    recognizer.energy_threshold         = 300
    recognizer.dynamic_energy_threshold = True

    update_ui('setStatus', 'LISTENING')
    update_ui('setListening', 'true')
    sfx.play('listen')

    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.4)
            try:
                audio = recognizer.listen(source, timeout=8, phrase_time_limit=12)
            except sr.WaitTimeoutError:
                update_ui('setStatus', 'ONLINE')
                update_ui('setListening', 'false')
                update_ui('addMessage', 'system', 'No input detected, sir.')
                _is_listening = False
                return

        update_ui('setStatus', 'PROCESSING')
        update_ui('setListening', 'false')

        try:
            text = recognizer.recognize_google(audio)
            threading.Thread(target=process_input, args=(text,), daemon=True).start()
        except sr.UnknownValueError:
            update_ui('setStatus', 'ONLINE')
            update_ui('addMessage', 'system', 'Could not understand audio, sir.')
            sfx.play('error')
        except sr.RequestError as e:
            update_ui('setStatus', 'ONLINE')
            update_ui('addMessage', 'system', f'Speech error: {e}')
            sfx.play('error')
    except OSError as e:
        update_ui('setStatus', 'ONLINE')
        update_ui('addMessage', 'system', f'Microphone error: {e}')
        sfx.play('error')
    finally:
        _is_listening = False
