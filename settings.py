"""
settings.py — JARVIS settings manager
Reads/writes settings.json for persistent config

Updates in this version:
  Update 3  — notif_enabled, notif_whitelist
  Update 5  — personality_mode
  Update 6  — reset_to_defaults() called on every startup
  Update 7  — screen_check_interval, screen_react_prob, screen_react_gap (PROTECTED)
  Phase 1   — Settings file moved to %APPDATA%\\JARVIS\\jarvis_settings.json
              so user prefs and API keys survive app updates forever.
              reset_to_defaults() is now non-destructive: only adds new keys,
              never overwrites existing user values.
              All user-preference keys added to PROTECTED_KEYS.
"""
import json
import os
import shutil

# ── AppData storage path (survives app installs and updates) ──────────────────
_APPDATA        = os.environ.get('APPDATA', os.path.expanduser('~'))
JARVIS_DATA_DIR = os.path.join(_APPDATA, 'JARVIS')
SETTINGS_FILE   = os.path.join(JARVIS_DATA_DIR, 'jarvis_settings.json')

# ── Old path — only used once for one-time migration ─────────────────────────
_OLD_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jarvis_settings.json')


DEFAULTS = {
    # ── API Keys ────────────────────────────────────────────
    'gemini_api_key':         '',
    'gemini_model':           'gemini-3.1-flash-lite-preview',
    'steam_api_key':          '',
    'steam_user_id':          '',
    'spotify_client_id':      '',
    'spotify_client_secret':  '',
    # ── Voice & Briefing ────────────────────────────────────
    'voice':                  'en-GB-RyanNeural',
    'briefing_hour':          8,
    'briefing_minute':        0,
    # ── General ─────────────────────────────────────────────
    'username':               'sir',
    'clap_threshold':         4500,
    'screen_awareness':       True,
    # ── Update 5: Personality Mode ──────────────────────────
    'personality_mode':       'normal',
    # ── Update 3: Notification Reader ──────────────────────
    'notif_enabled':          True,
    'notif_whitelist':        'discord,steam,whatsapp,telegram,gmail,outlook,spotify',
    # ── Update 7: Screen Watcher Tuning (PROTECTED) ─────────
    'screen_check_interval':  15,
    'screen_react_prob':      0.75,
    'screen_react_gap':       35,
}

# ── Keys that are NEVER overwritten by reset_to_defaults() ───────────────────
# Phase 1 change: ALL user-preference keys are now protected.
# Anything a user can configure in-app must persist across restarts and updates.
PROTECTED_KEYS = frozenset({
    # API credentials
    'gemini_api_key',
    'gemini_model',           # ← ADDED: model selector choice persists
    'steam_api_key',
    'steam_user_id',
    'spotify_client_id',
    'spotify_client_secret',
    # User preferences — these are personal config, never reset them
    'username',               # ← ADDED
    'voice',                  # ← ADDED
    'clap_threshold',         # ← ADDED: user-calibrated mic sensitivity
    'briefing_hour',          # ← ADDED
    'briefing_minute',        # ← ADDED
    'personality_mode',       # ← ADDED
    'notif_enabled',          # ← ADDED
    'notif_whitelist',        # ← ADDED
    'screen_awareness',       # ← ADDED
    # Screen watcher calibration
    'screen_check_interval',
    'screen_react_prob',
    'screen_react_gap',
})


def _ensure_data_dir():
    """Create %APPDATA%\\JARVIS\\ if it doesn't exist yet."""
    os.makedirs(JARVIS_DATA_DIR, exist_ok=True)


def _migrate_old_settings():
    """
    One-time migration: if settings.json exists in the old app directory
    but not yet in AppData, copy it over so the user doesn't lose their keys.
    Runs silently — no action if already migrated or no old file exists.
    """
    if os.path.exists(SETTINGS_FILE):
        return  # already in AppData, nothing to do
    if os.path.exists(_OLD_SETTINGS_FILE):
        try:
            shutil.copy2(_OLD_SETTINGS_FILE, SETTINGS_FILE)
            print(f"[Settings] Migrated settings to {SETTINGS_FILE}")
        except Exception as e:
            print(f"[Settings] Migration copy failed: {e}")


def load():
    _ensure_data_dir()
    _migrate_old_settings()

    if not os.path.exists(SETTINGS_FILE):
        save(DEFAULTS)
        return dict(DEFAULTS)
    try:
        with open(SETTINGS_FILE, 'r') as f:
            data = json.load(f)
        # Merge: defaults fill in any missing keys from older save files
        merged = dict(DEFAULTS)
        merged.update(data)
        return merged
    except Exception:
        return dict(DEFAULTS)


def save(data):
    _ensure_data_dir()
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Settings save error: {e}")
        return False


def reset_to_defaults():
    """
    Phase 1 change — NON-DESTRUCTIVE reset.

    Old behavior: wipe all non-protected keys back to defaults (bad for a real app).
    New behavior: only ADD keys that don't exist in the file yet.
                  Never overwrites any key the user has already set.

    This means updates that introduce brand-new settings keys will automatically
    get their defaults on the next JARVIS launch, while every existing preference
    the user configured stays untouched forever.
    """
    _ensure_data_dir()
    _migrate_old_settings()

    current = load()
    added_keys = []

    for key, default_val in DEFAULTS.items():
        if key not in current:
            current[key] = default_val
            added_keys.append(key)

    if added_keys:
        save(current)
        print(f"[Settings] Added {len(added_keys)} new default key(s): {sorted(added_keys)}")
    else:
        print("[Settings] Settings up to date.")


def get(key, fallback=None):
    return load().get(key, fallback)


def set_value(key, value):
    data = load()
    data[key] = value
    return save(data)
