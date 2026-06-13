"""
clap_listener.py — fixed clap detection
Double clap:
  - If JARVIS NOT running → launch it
  - If JARVIS IS running (headless) → signal server to show the window
"""

import pyaudio
import audioop
import time
import subprocess
import sys
import os
import psutil
import requests

# ── Tuning ─────────────────────────────────────────────────
CHUNK           = 512
FORMAT          = pyaudio.paInt16
CHANNELS        = 1
RATE            = 44100
CLAP_RMS        = 4500
SPIKE_REQUIRED  = 3000
MIN_CLAP_GAP    = 0.10
MAX_DOUBLE_GAP  = 0.80
COOLDOWN        = 3.0
SERVER_PORT     = 5000
SECRET_KEY      = "jarvis"
# ───────────────────────────────────────────────────────────

JARVIS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jarvis.py')


def is_jarvis_running():
    for p in psutil.process_iter(['cmdline']):
        try:
            if p.info['cmdline'] and 'jarvis.py' in ' '.join(p.info['cmdline']):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def signal_show_window():
    """Tell the headless JARVIS server to pop the window into view."""
    try:
        r = requests.post(
            f'http://127.0.0.1:{SERVER_PORT}/show',
            json={'token': SECRET_KEY},
            timeout=2
        )
        return r.status_code == 200
    except Exception as e:
        print(f"[JARVIS Clap] Could not signal server: {e}")
        return False


def run():
    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT, channels=CHANNELS,
        rate=RATE, input=True, frames_per_buffer=CHUNK
    )

    print("[JARVIS] Clap listener active. 👏👏 to summon JARVIS.")

    prev_rms       = 0
    last_clap_time = 0.0
    clap_count     = 0
    cooldown_until = 0.0

    while True:
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
        except Exception:
            time.sleep(0.05)
            continue

        now = time.time()

        if now < cooldown_until:
            time.sleep(0.02)
            prev_rms = 0
            continue

        rms   = audioop.rms(data, 2)
        spike = rms - prev_rms
        is_clap = (rms >= CLAP_RMS and spike >= SPIKE_REQUIRED)

        if is_clap:
            time_since_last = now - last_clap_time
            if time_since_last < MIN_CLAP_GAP:
                prev_rms = rms
                continue

            if clap_count == 1 and time_since_last <= MAX_DOUBLE_GAP:
                print("[JARVIS] Double clap detected!")
                clap_count     = 0
                cooldown_until = now + COOLDOWN

                if is_jarvis_running():
                    # JARVIS is running headless — signal it to show the window
                    print("[JARVIS] Process found — signaling to show window...")
                    ok = signal_show_window()
                    if not ok:
                        print("[JARVIS] Signal failed — launching fresh instance.")
                        subprocess.Popen([sys.executable, JARVIS_PATH])
                else:
                    print("[JARVIS] Launching JARVIS...")
                    subprocess.Popen([sys.executable, JARVIS_PATH])
            else:
                clap_count     = 1
                last_clap_time = now
                print(f"[JARVIS] First clap (RMS:{rms} spike:{spike})")

        if clap_count == 1 and (now - last_clap_time) > MAX_DOUBLE_GAP:
            clap_count = 0

        prev_rms = rms
        time.sleep(0.005)


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print("\n[JARVIS] Clap listener stopped.")
