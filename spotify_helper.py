"""
spotify_helper.py — Spotify control
Get free keys at: developer.spotify.com → create app → set redirect URI to http://localhost:8888/callback
"""

# ── GET THESE FREE AT developer.spotify.com ───────────────
# Leave these blank — JARVIS reads them from Settings (⚙ in the UI)
SPOTIFY_CLIENT_ID     = ""
SPOTIFY_CLIENT_SECRET = ""
# ──────────────────────────────────────────────────────────

import requests
import subprocess
import base64
import threading
import time
import os

try:
    import psutil
    import win32gui
    import win32process
    _has_win32 = True
except Exception:
    _has_win32 = False


def _load_creds():
    """Always read fresh credentials from settings.json."""
    global SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
    try:
        import sys
        jarvis_dir = os.path.dirname(os.path.abspath(__file__))
        if jarvis_dir not in sys.path:
            sys.path.insert(0, jarvis_dir)
        import settings as cfg
        s = cfg.load()
        cid = s.get('spotify_client_id', '').strip()
        sec = s.get('spotify_client_secret', '').strip()
        if cid:
            SPOTIFY_CLIENT_ID     = cid
        if sec:
            SPOTIFY_CLIENT_SECRET = sec
    except Exception:
        pass

# ── Token cache ───────────────────────────────────────────
_token       = None
_token_expiry = 0


def _get_token():
    global _token, _token_expiry
    # Always reload creds in case user updated settings
    _load_creds()
    if _token and time.time() < _token_expiry:
        return _token
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET or 'PASTE' in SPOTIFY_CLIENT_ID:
        return None
    try:
        creds   = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
        encoded = base64.b64encode(creds.encode()).decode()
        r = requests.post(
            'https://accounts.spotify.com/api/token',
            headers={'Authorization': f'Basic {encoded}'},
            data={'grant_type': 'client_credentials'},
            timeout=8
        )
        if r.status_code == 200:
            data          = r.json()
            _token        = data['access_token']
            _token_expiry = time.time() + data.get('expires_in', 3600) - 60
            return _token
    except Exception:
        pass
    return None


def _open_uri(uri):
    subprocess.Popen(f'start "" "{uri}"', shell=True)


# ── Current song (reads Spotify window title) ─────────────

def get_current_song():
    """Gets current song from Spotify window title — no API key needed."""
    if not _has_win32:
        return "Could not read Spotify window title on this system, sir."
    result = []
    def enum_cb(hwnd, _):
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['pid'] == pid and 'spotify' in proc.info['name'].lower():
                    title = win32gui.GetWindowText(hwnd)
                    if title and title != 'Spotify':
                        result.append(title)
        except Exception:
            pass
    win32gui.EnumWindows(enum_cb, None)
    if result:
        return f"Currently playing: {result[0]}, sir."
    return "Spotify doesn't appear to be playing anything, sir."


# ── Playlist search ───────────────────────────────────────

KNOWN_PLAYLISTS = {
    'liked songs':    'spotify:collection:tracks',
    'my liked songs': 'spotify:collection:tracks',
    'liked':          'spotify:collection:tracks',
}


def search_and_open_playlist(query):
    name = query.lower().strip()
    for key, uri in KNOWN_PLAYLISTS.items():
        if key in name or name in key:
            _open_uri(uri)
            return f"Opening your {key}, sir."

    token = _get_token()
    if token:
        try:
            r = requests.get(
                'https://api.spotify.com/v1/search',
                headers={'Authorization': f'Bearer {token}'},
                params={'q': query, 'type': 'playlist', 'limit': 1},
                timeout=8
            )
            if r.status_code == 200:
                items = r.json().get('playlists', {}).get('items', [])
                if items and items[0]:
                    uri  = items[0]['uri']
                    name = items[0]['name']
                    _open_uri(uri)
                    return f"Opening '{name}' on Spotify, sir."
        except Exception:
            pass

    _open_uri(f'spotify:search:{query}')
    return f"Searching for '{query}' on Spotify, sir."


def open_liked_songs():
    _open_uri('spotify:collection:tracks')
    return "Opening your liked songs, sir."


# ── Play song / artist ────────────────────────────────────

def play_song(song_name):
    """Search for a song and open it in Spotify — auto-plays via URI."""
    token = _get_token()
    if token:
        try:
            r = requests.get(
                'https://api.spotify.com/v1/search',
                headers={'Authorization': f'Bearer {token}'},
                params={'q': song_name, 'type': 'track', 'limit': 1},
                timeout=8
            )
            if r.status_code == 200:
                items = r.json().get('tracks', {}).get('items', [])
                if items:
                    track  = items[0]
                    uri    = track['uri']      # e.g. spotify:track:XXXXX
                    name   = track['name']
                    artist = track['artists'][0]['name']
                    # Open the track URI directly — Spotify auto-plays it
                    _open_uri(uri)
                    return f"Playing '{name}' by {artist} on Spotify, sir."
        except Exception:
            pass

    # Fallback: open search and press Enter after a delay to play top result
    _open_uri(f'spotify:search:{song_name}')
    # Give Spotify time to load, then press Enter to play top result
    threading.Thread(target=_press_enter_after_delay, daemon=True).start()
    return f"Searching for '{song_name}' on Spotify, sir."


def _press_enter_after_delay():
    """Press Enter after Spotify loads search results to play top result."""
    import time
    try:
        import pyautogui
        time.sleep(2.5)          # Wait for Spotify to load results
        pyautogui.press('enter') # Select top result
        time.sleep(0.3)
        pyautogui.press('enter') # Play it
    except Exception as e:
        print(f"[Spotify] Enter press error: {e}")


def play_artist(artist_name):
    """Search for an artist and open their page in Spotify."""
    token = _get_token()
    if token:
        try:
            r = requests.get(
                'https://api.spotify.com/v1/search',
                headers={'Authorization': f'Bearer {token}'},
                params={'q': artist_name, 'type': 'artist', 'limit': 1},
                timeout=8
            )
            if r.status_code == 200:
                items = r.json().get('artists', {}).get('items', [])
                if items:
                    artist = items[0]
                    uri    = artist['uri']
                    name   = artist['name']
                    _open_uri(uri)
                    return f"Opening {name} on Spotify, sir."
        except Exception:
            pass

    _open_uri(f'spotify:search:{artist_name}')
    return f"Searching for '{artist_name}' on Spotify, sir."


# ── Sleep timer ───────────────────────────────────────────

_sleep_timer_thread = None


def set_music_sleep_timer(seconds):
    """Stop music after X seconds."""
    global _sleep_timer_thread

    def _stop():
        time.sleep(seconds)
        import ctypes
        VK_MEDIA_STOP = 0xB2
        ctypes.windll.user32.keybd_event(VK_MEDIA_STOP, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_MEDIA_STOP, 0, 2, 0)

    _sleep_timer_thread = threading.Thread(target=_stop, daemon=True)
    _sleep_timer_thread.start()

    mins = seconds // 60
    return (f"Music will stop in {mins} minute{'s' if mins>1 else ''}, sir."
            if mins else f"Music will stop in {seconds} seconds, sir.")


# ── Steam sale check ──────────────────────────────────────

def check_steam_sale(appid, game_name):
    """Check if a Steam game is currently on sale."""
    try:
        r = requests.get(
            f'https://store.steampowered.com/api/appdetails',
            params={'appids': appid, 'cc': 'dk', 'l': 'english'},
            timeout=8
        )
        data = r.json().get(str(appid), {}).get('data', {})
        if not data:
            return f"Could not find store data for {game_name}, sir."

        price_data = data.get('price_overview', {})
        if not price_data:
            return f"{game_name} appears to be free to play, sir."

        discount = price_data.get('discount_percent', 0)
        final    = price_data.get('final_formatted', 'N/A')
        initial  = price_data.get('initial_formatted', 'N/A')

        if discount > 0:
            return (f"{game_name} is currently on sale, sir. "
                    f"{discount}% off — {initial} down to {final}. I'd recommend grabbing it.")
        else:
            return f"{game_name} is not currently on sale, sir. Full price is {final}."
    except Exception as e:
        return f"Could not check Steam store, sir. {e}"
