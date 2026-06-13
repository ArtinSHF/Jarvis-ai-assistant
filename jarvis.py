"""
jarvis.py — Main JARVIS launcher
Supports two modes:
  - Normal: python jarvis.py          → full UI + greeting
  - Headless: python jarvis.py --headless  → background only, no UI, no greeting
The VBS startup script should launch with --headless

Update 6: settings.reset_to_defaults() is called at the VERY start of main(),
before brain or any other module loads settings. Protected keys are preserved.

Phase 3: updater.check_for_updates() runs in a background thread from on_start()
so JARVIS auto-updates from GitHub Releases on every launch.
"""

import webview
import threading
import os
import time
import sys

window_ref      = None
call_window_ref = None
HEADLESS        = '--headless' in sys.argv


class JarvisAPI:
    def start_listening(self):
        import brain
        threading.Thread(target=brain.listen_cycle, daemon=True).start()
        return True

    def send_text(self, text):
        import brain
        threading.Thread(target=brain.process_input, args=(text,), daemon=True).start()
        return True

    def minimize_window(self):
        if window_ref:
            window_ref.minimize()

    def close_window(self):
        if window_ref:
            window_ref.destroy()

    def open_call_mode(self):
        open_call_mode()

    def toggle_fullscreen(self):
        if window_ref:
            window_ref.toggle_fullscreen()

    def get_settings(self):
        import settings as cfg
        return cfg.load()

    def save_settings(self, data):
        import settings as cfg
        import brain
        ok = cfg.save(data)
        if ok:
            brain.reload_settings()
        return ok


class CallAPI:
    def start_listening(self):
        import brain
        threading.Thread(target=brain.listen_cycle, daemon=True).start()
        return True

    def exit_call_mode(self):
        close_call_mode()

    def close_window(self):
        close_call_mode()


def show_main_window():
    """Pull the existing background process into view — called by clap listener or phone."""
    global window_ref
    if window_ref:
        try:
            window_ref.show()
            window_ref.restore()
            import brain, sfx
            sfx.play('startup')
            time.sleep(2.8)
            greeting = "Good day, sir. All systems are online and fully operational. I am ready to assist you."
            brain.update_ui('addMessage', 'jarvis', greeting)
            brain.speak(greeting)
            time.sleep(4)
            briefing_prompt = "Would you like a daily briefing, sir? I can give you the weather, time, news, and your reminders."
            brain.update_ui('addMessage', 'jarvis', briefing_prompt)
            brain.speak(briefing_prompt)
        except Exception as e:
            print(f"[JARVIS] show_window error: {e}")


def open_call_mode():
    global call_window_ref
    import brain
    if call_window_ref:
        return
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'call_mode.html')
    call_window_ref = webview.create_window(
        'J.A.R.V.I.S — CALL',
        html_path,
        js_api=CallAPI(),
        width=300,
        height=500,
        on_top=True,
        background_color='#020810',
        confirm_close=False,
        resizable=False,
    )
    brain.set_call_window(call_window_ref)
    if window_ref:
        window_ref.hide()


def close_call_mode():
    global call_window_ref
    import brain
    brain.set_call_window(None)
    if call_window_ref:
        call_window_ref.destroy()
        call_window_ref = None
    if window_ref:
        window_ref.show()


def on_start():
    """Called after webview window is ready."""
    import brain, sfx
    if HEADLESS:
        print("[JARVIS] Headless mode — waiting for clap or phone connection.")
        # ── Phase 3: check for updates silently in headless mode ──────────────
        import updater
        threading.Thread(target=updater.check_for_updates, daemon=True).start()
        # ─────────────────────────────────────────────────────────────────────
        return

    sfx.play('startup')
    time.sleep(2.8)
    greeting = "Good day, sir. All systems are online and fully operational. I am ready to assist you."
    brain.update_ui('addMessage', 'jarvis', greeting)
    brain.speak(greeting)
    time.sleep(4)
    briefing_prompt = "Would you like a daily briefing, sir? I can give you the weather, time, news, and your reminders."
    brain.update_ui('addMessage', 'jarvis', briefing_prompt)
    brain.speak(briefing_prompt)

    # ── Phase 3: check for updates in background after greeting ───────────────
    import updater
    updater.set_message_callback(lambda t: brain.update_ui('addMessage', 'jarvis', t))
    threading.Thread(target=updater.check_for_updates, daemon=True).start()
    # ─────────────────────────────────────────────────────────────────────────


def main():
    global window_ref

    # ── UPDATE 6: Reset settings to defaults on every launch ──
    import settings as cfg
    cfg.reset_to_defaults()
    # ──────────────────────────────────────────────────────────

    import brain, server

    api       = JarvisAPI()
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')

    window_ref = webview.create_window(
        'J.A.R.V.I.S',
        html_path,
        js_api=api,
        width=1100,
        height=720,
        min_size=(900, 600),
        background_color='#020810',
        confirm_close=False,
        hidden=HEADLESS,
    )

    brain.set_window(window_ref)
    server.start(brain, jarvis_win=window_ref)
    webview.start(on_start, debug=False)


if __name__ == '__main__':
    main()
