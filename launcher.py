"""
launcher.py — JARVIS Launcher
==============================
Compiled to JARVIS.exe via build_launcher.bat.

On crash, writes full error output to:
    %APPDATA%\JARVIS\jarvis.log
and shows an error dialog pointing to it.
"""

import os
import sys
import subprocess
import ctypes
import datetime


def show_error(title, message):
    ctypes.windll.user32.MessageBoxW(0, message, f"JARVIS — {title}", 0x10)
    sys.exit(1)


def get_log_path():
    appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
    log_dir = os.path.join(appdata, 'JARVIS')
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, 'jarvis.log')


def main():
    base_dir   = os.path.dirname(os.path.abspath(sys.executable))
    python_exe = os.path.join(base_dir, 'python', 'python.exe')
    jarvis_py  = os.path.join(base_dir, 'jarvis.py')
    log_path   = get_log_path()

    # ── Sanity checks ─────────────────────────────────────────────────────────
    if not os.path.exists(python_exe):
        show_error(
            "Setup Required",
            f"Embedded Python not found.\n\n"
            f"Expected: {python_exe}\n\n"
            f"Please run setup_package.py first."
        )

    if not os.path.exists(jarvis_py):
        show_error(
            "Missing File",
            f"jarvis.py not found.\n\n"
            f"Expected: {jarvis_py}\n\n"
            f"Make sure all JARVIS files are in the same folder as JARVIS.exe."
        )

    # ── Launch with log ────────────────────────────────────────────────────────
    with open(log_path, 'w', encoding='utf-8') as log:
        log.write(f"JARVIS Launch Log — {datetime.datetime.now()}\n")
        log.write(f"Base dir : {base_dir}\n")
        log.write(f"Python   : {python_exe}\n")
        log.write(f"Script   : {jarvis_py}\n")
        log.write("=" * 60 + "\n\n")
        log.flush()

        result = subprocess.run(
            [python_exe, jarvis_py] + sys.argv[1:],
            cwd=base_dir,
            stdout=log,
            stderr=log
        )

    # ── If JARVIS exited with an error, show where the log is ─────────────────
    if result.returncode != 0:
        # Read last 30 lines of the log to show in the dialog
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            tail = "".join(lines[-30:]).strip()
        except Exception:
            tail = "(could not read log)"

        show_error(
            "Crash",
            f"JARVIS crashed (exit code {result.returncode}).\n\n"
            f"Last output:\n{tail[:800]}\n\n"
            f"Full log: {log_path}"
        )

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
