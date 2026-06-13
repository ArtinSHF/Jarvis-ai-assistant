"""
build_release.py — JARVIS Release Builder
==========================================
Run this from your JARVIS folder every time you want to push an update.
Creates jarvis_code_vX.Y.Z.zip — attach this file to your GitHub Release.

Usage:
    py -3.11 build_release.py

What it zips (code files only — NOT python/ folder or settings):
  All .py files, .html files, version.txt, requirements.txt
"""

import os
import sys
import zipfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Every file that goes into a code update release.
# python/ is intentionally excluded — it never changes for normal code updates.
# jarvis_settings.json is intentionally excluded — that's user data.
RELEASE_FILES = [
    'jarvis.py',
    'brain.py',
    'server.py',
    'task_executor.py',
    'clap_listener.py',
    'screen_watcher.py',
    'notification_listener.py',
    'reminder_engine.py',
    'spotify_helper.py',
    'settings.py',
    'notes.py',
    'sfx.py',
    'updater.py',
    'index.html',
    'mobile.html',
    'call_mode.html',
    'version.txt',
    'requirements.txt',
]


def main():
    # Read current version
    version_path = os.path.join(BASE_DIR, 'version.txt')
    if not os.path.exists(version_path):
        print("[!] version.txt not found.")
        print("    Create it in your JARVIS folder with just the version number, e.g: 1.0.1")
        sys.exit(1)

    with open(version_path) as f:
        version = f.read().strip().lstrip('v')

    zip_name = f"jarvis_code_v{version}.zip"
    zip_path = os.path.join(BASE_DIR, zip_name)

    print(f"\nBuilding release for v{version}...")
    print("─" * 50)

    missing = []
    included = []

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for filename in RELEASE_FILES:
            full = os.path.join(BASE_DIR, filename)
            if os.path.exists(full):
                z.write(full, filename)
                size = os.path.getsize(full)
                print(f"  + {filename:<40} ({size:,} bytes)")
                included.append(filename)
            else:
                print(f"  - {filename:<40} MISSING — skipped")
                missing.append(filename)

    zip_size = os.path.getsize(zip_path)
    print("─" * 50)
    print(f"  {len(included)} files  |  {zip_size:,} bytes  →  {zip_name}")

    if missing:
        print(f"\n  [!] {len(missing)} file(s) missing: {missing}")
        print("      These were skipped. Make sure the filenames are correct.")

    print(f"""
Done! Now:

  1. Bump version.txt to the next version for your NEXT release
     (leave it as {version} for now — it gets distributed in this zip)

  2. Go to: https://github.com/yourusername/jarvis/releases/new
     - Tag:    v{version}
     - Title:  JARVIS v{version}
     - Attach: {zip_name}
     - Publish

  3. Every installed JARVIS will auto-update on next launch.
""")


if __name__ == '__main__':
    main()
