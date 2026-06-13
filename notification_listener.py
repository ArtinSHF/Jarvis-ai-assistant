"""
notification_listener.py — JARVIS Windows Notification Reader (Update 3)

Polls the Windows notification SQLite database every 3 seconds.
Only speaks notifications from whitelisted apps.
Skips notifications that look like spam (very short, system noise, etc).
Never fires on startup — pre-loads existing IDs so only NEW notifications speak.

No extra packages required. Uses only stdlib (sqlite3, shutil, tempfile).
"""

import threading
import time
import sqlite3
import os
import re
import shutil
import tempfile

# ── State ─────────────────────────────────────────────────
_running        = False
_thread         = None
_speak_cb       = None
_message_cb     = None
_seen_ids       = set()
_enabled        = True
_whitelist      = ['discord', 'steam', 'whatsapp', 'telegram', 'gmail', 'outlook', 'spotify']
_POLL_INTERVAL  = 3   # seconds between DB polls

# Windows stores notifications here — same path on Win 10 and 11
NOTIF_DB = os.path.join(
    os.environ.get('LOCALAPPDATA', ''),
    'Microsoft', 'Windows', 'Notifications', 'wpndatabase.db'
)


# ── Helpers ───────────────────────────────────────────────

def _extract_text(xml_str: str) -> str:
    """Pull human-readable text out of a Windows toast notification XML payload."""
    if not xml_str:
        return ''
    try:
        texts = re.findall(r'<text[^>]*>([^<]+)</text>', xml_str)
        return ' — '.join(t.strip() for t in texts if t.strip())
    except Exception:
        return ''


def _is_whitelisted(handler_id: str) -> bool:
    """Return True if the notification's app is in the whitelist."""
    if not _whitelist:
        return True   # empty whitelist = allow everything
    h = (handler_id or '').lower()
    return any(w.lower() in h for w in _whitelist)


def _is_spam(text: str) -> bool:
    """Filter out noise: very short texts, blank notifications, etc."""
    if not text or len(text.strip()) < 6:
        return True
    spam_patterns = [
        r'^(\d+)$',                  # pure numbers
        r'^\.+$',                    # dots only
        r'^\s*$',                    # whitespace only
    ]
    for pat in spam_patterns:
        if re.match(pat, text.strip()):
            return True
    return False


def _open_db_copy():
    """
    Copy the notification DB to a temp file and open it read-only.
    Windows keeps an exclusive write lock on wpndatabase.db, but a file-copy
    approach works around that without needing any special COM/WinRT packages.
    Returns (conn, tmp_path) or (None, None) on failure.
    """
    if not os.path.exists(NOTIF_DB):
        return None, None
    try:
        tmp = tempfile.mktemp(suffix='_jarvis_notif.db')
        shutil.copy2(NOTIF_DB, tmp)
        conn = sqlite3.connect(tmp, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn, tmp
    except Exception as e:
        print(f"[NotifListener] DB copy error: {e}")
        return None, None


def _fetch_recent(conn):
    """
    Return rows from the Notification table.
    Handles schema differences between Windows 10 / 11 builds gracefully.
    """
    cur = conn.cursor()
    # Try the full join first (Windows 11 schema)
    try:
        cur.execute("""
            SELECT n.Id, n.Payload,
                   COALESCE(h.PrimaryId, n.HandlerId, '') AS AppId
            FROM   Notification n
            LEFT JOIN NotificationHandler h ON n.HandlerId = h.RecordId
            ORDER  BY n.ArrivalTime DESC
            LIMIT  30
        """)
        return cur.fetchall()
    except Exception:
        pass
    # Fallback: minimal schema (Windows 10)
    try:
        cur.execute("""
            SELECT Id, Payload, HandlerId AS AppId
            FROM   Notification
            ORDER  BY ArrivalTime DESC
            LIMIT  30
        """)
        return cur.fetchall()
    except Exception:
        pass
    return []


def _poll_loop():
    global _seen_ids, _running

    while _running:
        time.sleep(_POLL_INTERVAL)

        if not _running or not _enabled:
            continue

        conn, tmp_path = _open_db_copy()
        if conn is None:
            continue

        try:
            rows = _fetch_recent(conn)
        except Exception:
            rows = []
        finally:
            try:
                conn.close()
            except Exception:
                pass
            try:
                os.remove(tmp_path)
            except Exception:
                pass

        for row in rows:
            try:
                notif_id = row['Id']
            except Exception:
                continue

            if notif_id in _seen_ids:
                continue
            _seen_ids.add(notif_id)

            # App filter
            try:
                app_id = str(row['AppId'] or '')
            except Exception:
                app_id = ''

            if not _is_whitelisted(app_id):
                continue

            # Parse text from XML payload
            try:
                payload = str(row['Payload'] or '')
            except Exception:
                continue

            text = _extract_text(payload)
            if _is_spam(text):
                continue

            # Build a clean app name for announcement
            # AppId is usually something like "Discord.Discord_..._exe" or "Microsoft.Outlook...."
            parts = re.split(r'[!._]', app_id)
            app_name = next(
                (p for p in reversed(parts) if p and len(p) > 2 and not p[0].isdigit()),
                'System'
            )
            app_name = app_name.capitalize()

            announcement = f"Notification from {app_name}: {text}"

            if _message_cb:
                try:
                    _message_cb('jarvis', announcement)
                except Exception:
                    pass
            if _speak_cb:
                try:
                    _speak_cb(announcement)
                except Exception:
                    pass


def _preload_seen_ids():
    """
    Before the poll loop starts, read all EXISTING notification IDs so we
    don't replay old notifications on startup.
    """
    global _seen_ids
    conn, tmp_path = _open_db_copy()
    if conn is None:
        return
    try:
        cur = conn.cursor()
        cur.execute("SELECT Id FROM Notification")
        rows = cur.fetchall()
        _seen_ids = {r[0] for r in rows}
        print(f"[NotifListener] Pre-loaded {len(_seen_ids)} existing notification IDs.")
    except Exception as e:
        print(f"[NotifListener] Preload error: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
        try:
            os.remove(tmp_path)
        except Exception:
            pass


# ── Public API ────────────────────────────────────────────

def start(speak_callback, message_callback, whitelist=None, enabled=True):
    global _running, _thread, _speak_cb, _message_cb, _whitelist, _enabled

    if _running:
        return

    _speak_cb    = speak_callback
    _message_cb  = message_callback
    _enabled     = enabled

    if whitelist is not None:
        _whitelist = whitelist

    if not os.path.exists(NOTIF_DB):
        print(f"[NotifListener] DB not found at {NOTIF_DB} — notification listener disabled.")
        return

    _running = True
    _preload_seen_ids()

    _thread = threading.Thread(target=_poll_loop, daemon=True, name='JarvisNotifListener')
    _thread.start()
    print("[NotifListener] Windows notification listener active.")


def stop():
    global _running
    _running = False


def set_enabled(val: bool):
    global _enabled
    _enabled = val
    print(f"[NotifListener] {'Enabled' if val else 'Disabled'}.")


def update_whitelist(whitelist: list):
    global _whitelist
    _whitelist = whitelist
    print(f"[NotifListener] Whitelist updated: {_whitelist}")
