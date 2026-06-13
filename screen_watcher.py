"""
screen_watcher.py — JARVIS Screen Awareness Module v2

Update 7: Check interval, reaction probability, and minimum reaction gap are now
          runtime-configurable via settings — no code changes needed to tune them.
          Added update_check_interval(), update_react_prob(), update_react_gap().
          start() accepts these as parameters.

Update 8: Completely redesigned Gemini prompt forces specific, non-generic,
          format-varied reactions. Tracks last reaction to prevent repeated styles.
          Never "quite impressive sir" again.
"""

import threading
import time
import random
import base64
import io
import requests
import win32gui

# ── Runtime-configurable tuning ───────────────────────────
# These are updated from settings on startup and when settings are saved.
_check_interval = 15     # seconds between loop ticks
_react_prob     = 0.75   # base chance per tick to actually call the vision API
_react_gap      = 35     # minimum seconds between any two reactions

# Internal constants (not user-configurable)
MAX_INTEREST_BOOST   = 6
INTEREST_BOOST_ADD   = 3
INTEREST_BOOST_DECAY = 1
# ──────────────────────────────────────────────────────────

_running        = False
_thread         = None
_speak_cb       = None
_message_cb     = None
_gemini_url     = None
_enabled        = True
_last_react_at  = 0.0
_interest_boost = 0
_last_reaction  = ''   # Update 8: track last reaction to avoid repeated style


# ── Update 8: Redesigned prompt ──────────────────────────

def _build_screen_prompt() -> str:
    """Build the screen watcher prompt, injecting last reaction to force variety."""
    avoid_note = (
        f'\nYour PREVIOUS reaction was: "{_last_reaction}" — '
        'DO NOT use a similar style, tone, or subject matter.'
        if _last_reaction else ''
    )
    return f"""You are J.A.R.V.I.S silently observing the user's screen.{avoid_note}

Your task: decide if this exact screen moment is worth a short comment.

OUTPUT RULES — non-negotiable:
- Reply with ONLY the single word SKIP, or a single reaction (max 12 words)
- NEVER say anything generic: no "quite impressive sir", "interesting", "I see", "noted", "fascinating"
- React to the SPECIFIC, CONCRETE thing on screen — not the general category
- Vary your FORMAT every single time. Pick one of these styles and never repeat the same style back-to-back:
    • Blunt 3-word observation  (e.g. "That should hurt.")
    • Sarcastic question        (e.g. "Bold choice of cover, sir?")
    • Personally offended       (e.g. "I helped build that loadout.")
    • Impressed by one detail   (e.g. "That headshot angle was geometry.")
    • Dry one-liner             (e.g. "Physics engine disagrees, sir.")
    • Unexpected comparison     (e.g. "That explosion had opinions.")

ALWAYS SKIP if you see:
- A J.A.R.V.I.S or JARVIS chat interface
- Any AI chat, assistant, or chatbot window
- Discord, WhatsApp, or any text/chat messaging app
- A plain desktop, file explorer, control panel, or settings screen
- A video paused or buffering, loading screen, or static wallpaper
- A browser tab with no dramatic or notable visual content

React ONLY to (and ONLY to something specific, not vague):
- Active gameplay: a specific kill, death, explosion, clutch, rank change, achievement — name what happened
- Creative work: a Blender render completing, a specific bug fixed on screen, code running for first time
- Something visually absurd, dramatic, or hilarious on screen RIGHT NOW
- A result, score, or outcome that just appeared with a concrete number or name

The reaction must feel like it could ONLY have been said about THIS exact frame.
Output ONLY "SKIP" or the reaction. No punctuation at the end unless it's '?' or '!'"""


# ── JARVIS window detection ───────────────────────────────

def _is_jarvis_focused() -> bool:
    """Returns True if any JARVIS window is the current foreground window."""
    try:
        hwnd  = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd).lower()
        return 'j.a.r.v.i.s' in title or 'jarvis' in title
    except Exception:
        return False


# ── Screen capture ────────────────────────────────────────

def _capture_b64() -> str | None:
    """Grabs primary monitor, scales to 640×360, returns base64 JPEG. In-memory only."""
    try:
        import mss
        from PIL import Image
        with mss.mss() as sct:
            raw = sct.grab(sct.monitors[1])
            img = Image.frombytes('RGB', raw.size, raw.bgra, 'raw', 'BGRX')
        img.thumbnail((640, 360), Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=55, optimize=False)
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"[ScreenWatcher] Capture error: {e}")
        return None


# ── Gemini Vision call ────────────────────────────────────

def _ask_vision(image_b64: str) -> str | None:
    """One-shot Gemini vision call with the updated prompt. Returns reaction or None."""
    try:
        payload = {
            "contents": [{
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
                    {"text": _build_screen_prompt()}
                ]
            }],
            "generationConfig": {
                "temperature": 1.1,    # slightly higher for more creative variety
                "maxOutputTokens": 50
            }
        }
        r    = requests.post(_gemini_url, json=payload, timeout=15)
        data = r.json()
        if 'candidates' not in data:
            return None
        return data['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        print(f"[ScreenWatcher] Vision API error: {e}")
        return None


def _should_skip_reply(reply: str) -> bool:
    """True if Gemini said SKIP or returned something unusable."""
    if not reply:
        return True
    upper = reply.upper().strip()
    if upper == 'SKIP' or upper.startswith('SKIP'):
        return True
    if len(reply.strip('. ')) < 4:
        return True
    return False


# ── Main watch loop ───────────────────────────────────────

def _watch_loop():
    global _interest_boost, _last_react_at, _running, _last_reaction

    while _running:
        time.sleep(_check_interval)

        if not _running:
            break

        try:
            if not _enabled:
                continue

            if _is_jarvis_focused():
                continue

            # Probabilistic gate — boosts when interest is high
            prob = min(_react_prob + _interest_boost * 0.08, 0.90)
            if random.random() > prob:
                _interest_boost = max(0, _interest_boost - INTEREST_BOOST_DECAY)
                continue

            # Rate-limit gate
            if time.time() - _last_react_at < _react_gap:
                continue

            b64 = _capture_b64()
            if not b64 or not _gemini_url:
                continue

            reply = _ask_vision(b64)

            if _should_skip_reply(reply):
                _interest_boost = max(0, _interest_boost - INTEREST_BOOST_DECAY)
                continue

            reply = reply.strip().strip('"\'')

            _last_react_at  = time.time()
            _last_reaction  = reply   # Update 8: remember for next prompt
            _interest_boost = min(_interest_boost + INTEREST_BOOST_ADD, MAX_INTEREST_BOOST)

            if _message_cb:
                _message_cb('jarvis', reply)
            if _speak_cb:
                _speak_cb(reply)

        except Exception as e:
            print(f"[ScreenWatcher] Loop error: {e}")


# ── Public API ────────────────────────────────────────────

def start(speak_callback, message_callback, gemini_url: str, enabled: bool = True,
          check_interval: float = 15, react_prob: float = 0.75, react_gap: float = 35):
    """
    Start the screen watcher background thread.
    Update 7: check_interval, react_prob, react_gap now come from settings.
    """
    global _running, _thread, _speak_cb, _message_cb, _gemini_url, _enabled
    global _check_interval, _react_prob, _react_gap

    if _running:
        return

    _speak_cb       = speak_callback
    _message_cb     = message_callback
    _gemini_url     = gemini_url
    _enabled        = enabled
    _check_interval = float(check_interval)
    _react_prob     = float(react_prob)
    _react_gap      = float(react_gap)

    _running = True
    _thread  = threading.Thread(target=_watch_loop, daemon=True, name='JarvisScreenWatcher')
    _thread.start()
    print(f"[ScreenWatcher] Active. interval={_check_interval}s prob={_react_prob} gap={_react_gap}s")


def stop():
    global _running
    _running = False
    print("[ScreenWatcher] Stopped.")


def set_enabled(val: bool):
    global _enabled
    _enabled = val
    print(f"[ScreenWatcher] {'Enabled' if val else 'Disabled'}.")


def update_gemini_url(url: str):
    global _gemini_url
    _gemini_url = url


# ── Update 7: Runtime tuning setters ─────────────────────

def update_check_interval(val):
    global _check_interval
    _check_interval = float(val)
    print(f"[ScreenWatcher] Check interval → {_check_interval}s")


def update_react_prob(val):
    global _react_prob
    _react_prob = float(val)
    print(f"[ScreenWatcher] Reaction probability → {_react_prob}")


def update_react_gap(val):
    global _react_gap
    _react_gap = float(val)
    print(f"[ScreenWatcher] Reaction gap → {_react_gap}s")
