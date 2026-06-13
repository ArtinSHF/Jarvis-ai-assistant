"""
sfx.py — JARVIS Sound Effects using Windows built-in Beep
No extra libraries needed.
"""
import winsound
import threading

SOUNDS = {
    'boot':       [(400,60),(600,60),(800,60),(1000,80),(1200,60),(1400,100)],
    'listen':     [(1200,80),(1400,60)],
    'processing': [(800,60),(1000,60)],
    'done':       [(1000,60),(1200,100)],
    'error':      [(500,100),(350,150)],
    'close':      [(1000,60),(800,60),(600,100)],
    'startup':    [(300,80),(500,80),(700,80),(900,80),(1100,80),(1300,150)],
    'reminder':   [(1000,100),(1000,100),(1200,200)],
}

def play(name):
    seq = SOUNDS.get(name, [])
    if seq:
        threading.Thread(
            target=lambda: [winsound.Beep(f, d) for f, d in seq],
            daemon=True
        ).start()
