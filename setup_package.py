"""
setup_package.py — JARVIS Embedded Python Bootstrapper
=======================================================
Run this ONCE from your regular Python 3.11 installation.
This downloads and configures a self-contained Python environment
so JARVIS can run as a standalone app without touching the user's system Python.

Usage:
    py -3.11 setup_package.py

What it does:
    1. Downloads Python 3.11.9 embeddable zip from python.org
    2. Extracts it to ./python/
    3. Patches python311._pth to enable pip and site-packages
    4. Installs pip into the embedded Python
    5. Installs all JARVIS requirements from requirements.txt
    6. Fixes pywin32 DLLs so win32gui/win32api work in embedded mode
"""

import os
import sys
import zipfile
import urllib.request
import subprocess
import shutil
import glob

# ── Config ────────────────────────────────────────────────────────────────────
PYTHON_VERSION  = "3.11.9"
EMBED_URL       = (
    f"https://www.python.org/ftp/python/{PYTHON_VERSION}/"
    f"python-{PYTHON_VERSION}-embed-amd64.zip"
)
GET_PIP_URL     = "https://bootstrap.pypa.io/get-pip.py"

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
PYTHON_DIR      = os.path.join(BASE_DIR, "python")
PYTHON_EXE      = os.path.join(PYTHON_DIR, "python.exe")
PTH_FILE        = os.path.join(PYTHON_DIR, "python311._pth")

# ─────────────────────────────────────────────────────────────────────────────

def _progress(block_num, block_size, total_size):
    if total_size > 0:
        pct = min(100, int(block_num * block_size * 100 / total_size))
        bar = ("█" * (pct // 5)).ljust(20)
        print(f"\r  [{bar}] {pct}%", end="", flush=True)

def download(url, dest, label=None):
    name = label or os.path.basename(dest)
    print(f"  Downloading {name}...")
    urllib.request.urlretrieve(url, dest, _progress)
    print()  # newline after progress bar

def section(title):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")

# ─────────────────────────────────────────────────────────────────────────────

def check_existing():
    """Warn if python/ already exists so we don't clobber a working setup."""
    if os.path.exists(PYTHON_DIR):
        print("\n[!] ./python/ folder already exists.")
        answer = input("    Delete it and re-run setup? (y/N): ").strip().lower()
        if answer == 'y':
            print("  Removing existing python/ folder...")
            shutil.rmtree(PYTHON_DIR)
        else:
            print("  Aborting. Delete ./python/ manually then re-run.")
            sys.exit(0)

def download_and_extract_python():
    section("Step 1 — Downloading Python 3.11.9 embeddable package")
    zip_path = os.path.join(BASE_DIR, "_python_embed_tmp.zip")
    download(EMBED_URL, zip_path, f"python-{PYTHON_VERSION}-embed-amd64.zip")

    print("  Extracting...")
    os.makedirs(PYTHON_DIR, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(PYTHON_DIR)
    os.remove(zip_path)
    print("  Done.")

def patch_pth_file():
    """
    The embeddable Python intentionally disables site-packages AND does not
    include the parent directory in sys.path. We fix both:

      1. Uncomment 'import site' → enables pip-installed packages
      2. Add 'Lib/site-packages' → explicit package path
      3. Add '..' → the JARVIS root folder (one level above python/)
         so that jarvis.py can import settings.py, brain.py, etc.

    Without (3), every local JARVIS module import fails with ModuleNotFoundError.
    """
    section("Step 2 — Patching python311._pth")
    if not os.path.exists(PTH_FILE):
        print(f"  [!] Could not find {PTH_FILE}")
        print("  This is unexpected — the embeddable zip may have changed format.")
        sys.exit(1)

    with open(PTH_FILE, 'r') as f:
        content = f.read()

    # 1. Uncomment 'import site'
    content = content.replace('#import site', 'import site')

    # 2. Add Lib/site-packages (pip packages)
    if 'Lib/site-packages' not in content:
        content = content.rstrip() + '\nLib/site-packages\n'

    # 3. Add .. (JARVIS root) so local .py files are importable
    lines = [l.strip() for l in content.splitlines()]
    if '..' not in lines:
        content = content.rstrip() + '\n..\n'

    with open(PTH_FILE, 'w') as f:
        f.write(content)

    print("  site-packages enabled.")
    print("  JARVIS root (..) added to sys.path.")

def install_pip():
    section("Step 3 — Installing pip into embedded Python")
    get_pip_path = os.path.join(PYTHON_DIR, "_get_pip_tmp.py")
    download(GET_PIP_URL, get_pip_path, "get-pip.py")

    result = subprocess.run(
        [PYTHON_EXE, get_pip_path, "--no-warn-script-location"],
        capture_output=True, text=True
    )
    os.remove(get_pip_path)

    if result.returncode != 0:
        print("  [!] pip install failed:")
        print(result.stderr)
        sys.exit(1)
    print("  pip installed.")

def install_requirements():
    section("Step 4 — Installing JARVIS requirements (this may take 3-5 min)")
    req_file = os.path.join(BASE_DIR, "requirements.txt")
    if not os.path.exists(req_file):
        print(f"  [!] requirements.txt not found at {req_file}")
        sys.exit(1)

    print("  Installing packages...\n")
    result = subprocess.run(
        [
            PYTHON_EXE, "-m", "pip", "install",
            "-r", req_file,
            "--no-warn-script-location"
        ],
        # Stream output live so user sees progress
        cwd=BASE_DIR
    )

    if result.returncode != 0:
        print("\n  [!] pip install failed.")
        print("  If pyaudio failed, that's a known Windows issue.")
        print("  Try: pip install pipwin && pipwin install pyaudio")
        print("  Then manually copy PyAudio wheel into ./python/Lib/site-packages/")
        sys.exit(1)
    print("\n  All packages installed.")

def fix_pywin32_dlls():
    """
    pywin32 requires pywintypes311.dll and pythoncom311.dll to be findable
    at runtime. In a regular Python install, pywin32_postinstall.py copies
    them to Windows\\System32. For embedded Python, we copy them directly
    into the python/ root directory instead, which is on the DLL search path.
    """
    section("Step 5 — Fixing pywin32 DLLs for embedded Python")
    pywin32_sys32 = os.path.join(PYTHON_DIR, 'Lib', 'site-packages', 'pywin32_system32')

    if not os.path.exists(pywin32_sys32):
        print("  pywin32_system32 folder not found — skipping.")
        print("  (pywin32 may not have installed correctly)")
        return

    dlls = glob.glob(os.path.join(pywin32_sys32, '*.dll'))
    copied = 0
    for dll_path in dlls:
        dest = os.path.join(PYTHON_DIR, os.path.basename(dll_path))
        if not os.path.exists(dest):
            shutil.copy2(dll_path, dest)
            print(f"  Copied: {os.path.basename(dll_path)}")
            copied += 1

    if copied == 0:
        print("  DLLs already in place.")
    else:
        print(f"  Fixed {copied} DLL(s).")

def verify_install():
    """Quick smoke-test: try importing the trickiest packages."""
    section("Step 6 — Verifying installation")
    test_imports = [
        ("win32gui",        "pywin32"),
        ("pygame",          "pygame"),
        ("flask",           "Flask"),
        ("mss",             "mss"),
        ("speech_recognition", "SpeechRecognition"),
        ("webview",         "pywebview"),
    ]
    all_ok = True
    for module, pip_name in test_imports:
        result = subprocess.run(
            [PYTHON_EXE, "-c", f"import {module}; print('OK')"],
            capture_output=True, text=True
        )
        status = "OK" if result.returncode == 0 else "FAIL"
        if result.returncode != 0:
            all_ok = False
        print(f"  import {module:<22} [{status}]")

    if not all_ok:
        print("\n  [!] Some imports failed. Check the errors above.")
        print("  Common fixes:")
        print("    pyaudio:  pip install pipwin && pipwin install pyaudio")
        print("    pywin32:  re-run setup_package.py")
    return all_ok

# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "═" * 60)
    print("  JARVIS — Embedded Python Setup")
    print("═" * 60)
    print(f"  Base dir : {BASE_DIR}")
    print(f"  Python   : {PYTHON_DIR}")

    check_existing()
    download_and_extract_python()
    patch_pth_file()
    install_pip()
    install_requirements()
    fix_pywin32_dlls()
    ok = verify_install()

    print("\n" + "═" * 60)
    if ok:
        print("  Setup complete! Embedded Python is ready.")
        print("  Next step: run build_launcher.bat to create JARVIS.exe")
    else:
        print("  Setup finished with warnings. Fix the failed imports above.")
    print("═" * 60 + "\n")

if __name__ == "__main__":
    main()
