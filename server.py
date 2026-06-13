"""
server.py — JARVIS Remote Mirror Server v4
- Ghost mode suppresses S0 Modern Standby
- /show endpoint: clap listener or phone can pull window into view
- /unlock: threaded, non-blocking, improved PIN timing
- Phone gets Edge TTS audio streamed as base64 (matches PC voice exactly)
- One-way mirror: PC→phone only when phone initiated
- /screenshot: returns live JPEG of primary monitor for phone screen viewer
- Fix 3: TTS uses BytesIO — zero disk writes, no stray temp files
- Update 9: blocks remote commands/listen while agent mode is active
"""

from flask import Flask, request, jsonify, send_file, Response
from flask_socketio import SocketIO, emit
import threading
import os
import io            # ← Fix 3: BytesIO for RAM-only TTS
import socket as _socket
import ctypes
import asyncio
import base64

# ── CONFIG ────────────────────────────────────────────────
SERVER_PORT = 5000
SECRET_KEY  = "jarvis"
PC_PIN      = "Arti2.11"
# ──────────────────────────────────────────────────────────

app      = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

_brain          = None
_jarvis_window  = None
_phone_sessions = set()
_remote_active  = False

# ── Ghost mode ────────────────────────────────────────────
ES_CONTINUOUS        = 0x80000000
ES_SYSTEM_REQUIRED   = 0x00000001
ES_AWAYMODE_REQUIRED = 0x00000040

def _keep_alive():
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
        )
        print("[JARVIS Server] Ghost mode active.")
    except Exception as e:
        print(f"[JARVIS Server] Ghost mode warning: {e}")


def get_local_ip():
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


def set_brain(brain_module):
    global _brain
    _brain = brain_module


def set_jarvis_window(win):
    global _jarvis_window
    _jarvis_window = win


def is_remote_active():
    return _remote_active


# ── Serve mobile UI ───────────────────────────────────────
@app.route('/')
def index():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mobile.html')
    return send_file(path)

@app.route('/ping')
def ping():
    return jsonify({'status': 'online', 'version': '4.0'})

# ── Settings Management ────────────────────────────────────
@app.route('/get_settings', methods=['GET'])
def get_settings_route():
    import settings as cfg
    return jsonify(cfg.load())

@app.route('/save_settings', methods=['POST'])
def save_settings_route():
    import settings as cfg, brain
    data = request.get_json(force=True) or {}
    s = cfg.load()
    s.update(data)
    ok = cfg.save(s)
    if ok:
        brain.reload_settings()
    return jsonify({'ok': ok})

# ── Show window endpoint ──────────────────────────────────
@app.route('/show', methods=['POST'])
def show_window():
    data  = request.json or {}
    token = data.get('token', '')
    if token != SECRET_KEY:
        return jsonify({'error': 'unauthorized'}), 401
    def _do_show():
        import jarvis as _jarvis
        _jarvis.show_main_window()
    threading.Thread(target=_do_show, daemon=True).start()
    return jsonify({'status': 'showing'})

# ── Unlock ────────────────────────────────────────────────
@app.route('/unlock', methods=['POST'])
def unlock():
    data  = request.json or {}
    token = data.get('token', '')
    if token != SECRET_KEY:
        return jsonify({'error': 'unauthorized'}), 401

    def _do_unlock():
        try:
            import pyautogui, time
            pyautogui.FAILSAFE = False
            pyautogui.press('shift');      time.sleep(0.8)
            pyautogui.press('esc');        time.sleep(0.3)
            pyautogui.press('space');      time.sleep(0.8)
            pyautogui.press('tab');        time.sleep(0.3)
            pyautogui.press('shift');      time.sleep(0.6)
            pyautogui.hotkey('ctrl', 'a'); time.sleep(0.2)
            pyautogui.press('backspace');  time.sleep(0.2)
            pyautogui.write(str(PC_PIN), interval=0.15)
            time.sleep(0.4)
            pyautogui.press('enter')
            print("[JARVIS Unlock] PIN submitted.")
        except Exception as e:
            print(f"[JARVIS Unlock] Error: {e}")

    threading.Thread(target=_do_unlock, daemon=True).start()
    return jsonify({'status': 'unlocked'})


# ── Screenshot endpoint (phone live screen viewer) ────────
@app.route('/screenshot')
def screenshot():
    token = request.args.get('token', '')
    if token != SECRET_KEY:
        return jsonify({'error': 'unauthorized'}), 401
    try:
        import mss
        from PIL import Image
        with mss.mss() as sct:
            raw = sct.grab(sct.monitors[1])
            img = Image.frombytes('RGB', raw.size, raw.bgra, 'raw', 'BGRX')
        img.thumbnail((1280, 720), Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=60, optimize=False)
        buf.seek(0)
        return Response(
            buf.getvalue(),
            mimetype='image/jpeg',
            headers={'Cache-Control': 'no-store, no-cache', 'Pragma': 'no-cache'}
        )
    except Exception as e:
        print(f"[JARVIS Screenshot] Error: {e}")
        return jsonify({'error': str(e)}), 500


# ── Fix 3: Edge TTS — BytesIO, zero temp files ────────────
async def _generate_tts_audio(text, voice="en-GB-RyanNeural"):
    """
    Generate TTS audio entirely in RAM using BytesIO.
    Returns base64-encoded MP3 string, or None on failure.
    No files are written to disk at any point.
    """
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice, rate="+5%", volume="+10%")
        buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"[JARVIS Server] TTS error: {e}")
        return None


# ── Wake-on-LAN ───────────────────────────────────────────
@app.route('/wake', methods=['POST'])
def wake():
    data  = request.json or {}
    token = data.get('token', '')
    mac   = data.get('mac', '')
    if token != SECRET_KEY:
        return jsonify({'error': 'unauthorized'}), 401
    try:
        import wol
        wol.send_magic_packet(mac)
        return jsonify({'status': 'sent'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── SocketIO ──────────────────────────────────────────────
@socketio.on('connect')
def on_connect():
    global _remote_active
    token = request.args.get('token', '')
    if token != SECRET_KEY:
        return False
    _phone_sessions.add(request.sid)
    _remote_active = True
    emit('status', {'msg': 'ONLINE', 'connected': True})
    print(f"[JARVIS Server] Phone connected: {request.sid}")

    def _show():
        import time
        time.sleep(0.5)
        if _jarvis_window:
            try:
                _jarvis_window.show()
                _jarvis_window.restore()
            except Exception:
                pass
        if _brain:
            _brain.update_ui('addMessage', 'system', '📱 Remote session active.', source='remote')

    threading.Thread(target=_show, daemon=True).start()


@socketio.on('disconnect')
def on_disconnect():
    global _remote_active
    _phone_sessions.discard(request.sid)
    if not _phone_sessions:
        _remote_active = False
    print("[JARVIS Server] Phone disconnected.")
    if _brain and not _phone_sessions:
        _brain.update_ui('addMessage', 'system', '📱 Remote session ended.')


@socketio.on('command')
def on_command(data):
    text = data.get('text', '').strip()
    if not text or not _brain:
        return

    # Update 9: block remote input while agent mode is running
    if getattr(_brain, '_agent_locked', False):
        emit('addMessage', {
            'role': 'system',
            'text': '⚙ Agent mode active — JARVIS is locked in. Command ignored, sir.'
        })
        return

    _brain.update_ui('addMessage', 'user', text, source='local')
    threading.Thread(
        target=_brain.process_input,
        args=(text,),
        kwargs={'source': 'remote'},
        daemon=True
    ).start()


@socketio.on('listen')
def on_listen(data):
    if not _brain:
        return

    # Update 9: block voice listen during agent mode
    if getattr(_brain, '_agent_locked', False):
        emit('addMessage', {
            'role': 'system',
            'text': '⚙ Agent mode active — voice input blocked, sir.'
        })
        return

    threading.Thread(target=_brain.listen_cycle, daemon=True).start()


# ── Push helpers ──────────────────────────────────────────
def broadcast(event, data):
    try:
        socketio.emit(event, data)
    except Exception as e:
        print(f"[JARVIS Server] Broadcast error: {e}")


def push_add_message(role, text, source='local'):
    if role == 'user':
        return
    if source == 'remote' or role == 'system':
        broadcast('addMessage', {'role': role, 'text': text})


def push_set_status(status, source='local'):
    if _remote_active and source == 'remote':
        broadcast('setStatus', {'status': status})


def push_set_listening(val, source='local'):
    if _remote_active and source == 'remote':
        broadcast('setListening', {'value': str(val).lower()})


def push_speak_text(text, source='local'):
    if source != 'remote' or not _phone_sessions:
        return

    def _gen_and_push():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                import settings as cfg
                voice = cfg.get('voice', 'en-GB-RyanNeural')
            except Exception:
                voice = 'en-GB-RyanNeural'
            # Fix 3: uses BytesIO internally — no temp files
            audio_b64 = loop.run_until_complete(_generate_tts_audio(text, voice))
            loop.close()
            if audio_b64:
                broadcast('speakAudio', {'audio': audio_b64, 'text': text})
        except Exception as e:
            print(f"[JARVIS Server] push_speak_text error: {e}")
            broadcast('speakText', {'text': text})

    threading.Thread(target=_gen_and_push, daemon=True).start()


# ── Start ─────────────────────────────────────────────────
def start(brain_module, jarvis_win=None):
    set_brain(brain_module)
    if jarvis_win:
        set_jarvis_window(jarvis_win)
    _keep_alive()

    ip   = get_local_ip()
    port = SERVER_PORT
    print(f"\n[JARVIS Server] Running at:")
    print(f"  Local WiFi:  http://{ip}:{port}")
    print(f"  Tailscale:   Use Tailscale IP:{port}")
    print(f"  Token:       {SECRET_KEY}\n")

    threading.Thread(
        target=lambda: socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True),
        daemon=True
    ).start()