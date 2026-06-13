"""
updater.py - JARVIS Auto-Updater
Checks GitHub Releases on every startup and self-updates if newer version found.

Set GITHUB_REPO below to your repo (e.g. "artinrexhepi/jarvis").
That is the only thing you ever need to change in this file.

Debug log is written to: AppData/JARVIS/updater.log
Check that file if the updater seems to not be working.
"""

import os
import sys
import time
import zipfile
import io
import subprocess
import traceback

import requests

# ── ONLY THING YOU CHANGE ─────────────────────────────────────────────────────
GITHUB_REPO = "ArtinSHF/Jarvis-ai-assistant"
# ─────────────────────────────────────────────────────────────────────────────

RELEASES_URL = "https://api.github.com/repos/" + GITHUB_REPO + "/releases/latest"
ASSET_PREFIX = "jarvis_code_"

_message_cb = None


def set_message_callback(cb):
    global _message_cb
    _message_cb = cb


# ── Logging ───────────────────────────────────────────────────────────────────

def _log(text):
    print("[Updater] " + text)
    try:
        log_dir = os.path.join(os.environ.get("APPDATA", ""), "JARVIS")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "updater.log")
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("[" + stamp + "] " + text + "\n")
    except Exception:
        pass


def _ui(text):
    _log(text)
    if _message_cb:
        try:
            _message_cb(text)
        except Exception:
            pass


# ── Path helpers ──────────────────────────────────────────────────────────────

def _install_dir():
    # Strategy 1: installed mode — sys.executable is python/python.exe
    # so two levels up gives the JARVIS root
    candidate = os.path.dirname(os.path.dirname(os.path.abspath(sys.executable)))
    if os.path.exists(os.path.join(candidate, "jarvis.py")):
        return candidate

    # Strategy 2: running jarvis.py directly
    candidate2 = os.path.dirname(os.path.abspath(sys.argv[0]))
    if os.path.exists(os.path.join(candidate2, "jarvis.py")):
        return candidate2

    return os.getcwd()


def _local_version():
    vfile = os.path.join(_install_dir(), "version.txt")
    try:
        with open(vfile, "r") as f:
            v = f.read().strip().lstrip("v")
            return v if v else "0.0.0"
    except FileNotFoundError:
        _log("version.txt not found at " + vfile + " — treating as 0.0.0")
        return "0.0.0"
    except Exception as e:
        _log("Could not read version.txt: " + str(e))
        return "0.0.0"


def _parse(v):
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except Exception:
        return (0, 0, 0)


# ── Main update check ─────────────────────────────────────────────────────────

def check_for_updates():
    try:
        # Wipe old log at start of each session
        try:
            log_path = os.path.join(os.environ.get("APPDATA", ""), "JARVIS", "updater.log")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("=== JARVIS Updater === " + time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
        except Exception:
            pass

        time.sleep(6)

        install = _install_dir()
        local   = _local_version()

        _log("Install dir   : " + install)
        _log("Local version : v" + local)
        _log("Checking      : " + RELEASES_URL)

        try:
            r = requests.get(
                RELEASES_URL,
                timeout=10,
                headers={"User-Agent": "JARVIS-Updater/1.0"}
            )
        except requests.exceptions.ConnectionError:
            _log("No internet connection — skipping.")
            return
        except requests.exceptions.Timeout:
            _log("Request timed out — skipping.")
            return

        _log("GitHub API status: " + str(r.status_code))

        if r.status_code == 404:
            _log("404 — repo not found OR no published releases yet.")
            _log("Make sure GITHUB_REPO = '" + GITHUB_REPO + "' is correct and the repo is public.")
            _log("Also make sure the release is PUBLISHED (not saved as draft).")
            return

        if r.status_code != 200:
            _log("Unexpected status " + str(r.status_code) + " — skipping.")
            return

        release  = r.json()
        tag      = release.get("tag_name", "").strip()
        latest   = tag.lstrip("v")
        is_draft = release.get("draft", False)

        _log("Latest release: " + tag + "  draft=" + str(is_draft))

        if not latest:
            _log("No tag_name in response — skipping.")
            return

        if is_draft:
            _log("Release is a DRAFT — publish it first.")
            return

        if _parse(latest) <= _parse(local):
            _log("Already up to date.")
            return

        _log("Update available: v" + local + " -> v" + latest)

        assets = release.get("assets", [])
        _log("Assets: " + str([a["name"] for a in assets]))

        zip_asset = next(
            (a for a in assets
             if a["name"].startswith(ASSET_PREFIX) and a["name"].endswith(".zip")),
            None
        )

        if not zip_asset:
            _log("No asset starting with '" + ASSET_PREFIX + "' found.")
            _log("Attach jarvis_code_vX.Y.Z.zip to the GitHub release.")
            return

        _log("Found: " + zip_asset["name"] + " (" + str(zip_asset["size"]) + " bytes)")
        _apply_update(latest, zip_asset["browser_download_url"], install)

    except Exception as e:
        _log("Unexpected error: " + str(e))
        _log(traceback.format_exc())


def _apply_update(new_version, url, install_dir):
    try:
        _ui("Update available: v" + new_version + " — downloading...")
        _log("Downloading from: " + url)

        resp  = requests.get(url, timeout=60, stream=True)
        total = int(resp.headers.get("content-length", 0))
        buf   = io.BytesIO()
        done  = 0

        for chunk in resp.iter_content(chunk_size=8192):
            buf.write(chunk)
            done += len(chunk)
            if total:
                print("\r[Updater] Downloading... " + str(int(done * 100 / total)) + "%",
                      end="", flush=True)
        print()
        _log("Downloaded " + str(done) + " bytes.")
        buf.seek(0)

        if not zipfile.is_zipfile(buf):
            _log("Downloaded file is not a valid zip — aborting.")
            _ui("Update failed: downloaded file was invalid.")
            return

        buf.seek(0)
        _ui("Installing v" + new_version + "...")

        with zipfile.ZipFile(buf, "r") as z:
            names = z.namelist()
            _log("Zip contains " + str(len(names)) + " files: " + str(names))
            for member in names:
                target = os.path.realpath(os.path.join(install_dir, member))
                if not target.startswith(os.path.realpath(install_dir)):
                    _log("Blocked unsafe path: " + member)
                    continue
                z.extract(member, install_dir)
                _log("Extracted: " + member)

        _log("All files extracted.")
        _ui("JARVIS updated to v" + new_version + " — restarting...")
        time.sleep(2)
        _restart(install_dir)

    except Exception as e:
        _log("Error during update: " + str(e))
        _log(traceback.format_exc())
        _ui("Update failed — check AppData/JARVIS/updater.log")


def _restart(install_dir):
    python = sys.executable
    script = os.path.join(install_dir, "jarvis.py")
    _log("Restarting: " + python + " " + script)
    subprocess.Popen([python, script] + sys.argv[1:], cwd=install_dir)
    os._exit(0)
