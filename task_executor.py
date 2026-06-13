"""
task_executor.py — JARVIS Autonomous Agent Engine  (Update 9)
Handles massive task prompts: sends to Gemini for a JSON plan, then executes
every step (mkdir / write_file / delete_file / run_cmd) end-to-end with no
user interaction required.

Triggered from brain.py when a prompt exceeds MASSIVE_PROMPT_THRESHOLD chars
or contains one of TASK_MARKERS.  While active, brain._agent_locked = True
blocks all other user input.
"""

import os
import json
import re
import shutil
import subprocess
import threading
import requests

# ── Config ─────────────────────────────────────────────────────────────────
MASSIVE_PROMPT_THRESHOLD = 500
TASK_MARKERS = (
    '[task_start]',
    '[begin example prompt]',
    '[project_start]',
    '[begin task]',
)
DEFAULT_WORKDIR  = os.path.expanduser(r'~\Desktop\JARVIS_Projects')
PLAN_TOKEN_LIMIT = 8192
PLAN_TIMEOUT     = 120
CMD_TIMEOUT      = 120

_executor_thread = None


# ── Detection ───────────────────────────────────────────────────────────────

def is_massive_prompt(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    for marker in TASK_MARKERS:
        if marker in lower:
            return True
    return len(text.strip()) >= MASSIVE_PROMPT_THRESHOLD


# ── Entry Point ─────────────────────────────────────────────────────────────

def run_task(text: str, update_ui_cb, speak_cb, message_cb, gemini_url: str):
    global _executor_thread

    def _worker():
        try:
            _announce_start(update_ui_cb, speak_cb, message_cb)
            plan = _plan_task(text, gemini_url, message_cb)
            if plan is None:
                _fail("Gemini failed to produce a valid execution plan.", update_ui_cb, speak_cb, message_cb)
                return
            task_summary = plan.get('task_summary', 'Unnamed task')
            steps        = plan.get('steps', [])
            if not steps:
                _fail("The plan contained zero steps.", update_ui_cb, speak_cb, message_cb)
                return
            message_cb('system', f'📋 AGENT PLAN: {task_summary} — {len(steps)} step(s) queued.')
            _execute_plan(steps, update_ui_cb, speak_cb, message_cb)
            _announce_done(task_summary, len(steps), update_ui_cb, speak_cb, message_cb)
        except Exception as e:
            _fail(f"Unhandled agent error: {e}", update_ui_cb, speak_cb, message_cb)
        finally:
            try:
                import brain
                brain._agent_locked = False
            except Exception:
                pass
            update_ui_cb('setAgentMode', 'false')

    _executor_thread = threading.Thread(target=_worker, daemon=True, name='JARVIS-Agent')
    _executor_thread.start()


# ── Planning ────────────────────────────────────────────────────────────────

_PLANNER_SYSTEM = """\
You are JARVIS's autonomous task execution engine.
The user has provided a full project guide, task description, or codebase to build.
Produce a strict JSON execution plan that JARVIS will run on Windows.

RESPONSE FORMAT — RESPOND WITH ONLY VALID JSON. NOTHING ELSE.
No prose. No markdown. No code fences. No explanation.

{
  "task_summary": "One sentence describing what you are building",
  "steps": [
    {"op": "mkdir",       "path": "ABSOLUTE_PATH",                       "description": "short desc"},
    {"op": "write_file",  "path": "ABSOLUTE_PATH", "content": "FULL CONTENT", "description": "short desc"},
    {"op": "run_cmd",     "cmd": "exact command",  "cwd": "ABSOLUTE_PATH",    "description": "short desc"},
    {"op": "delete_file", "path": "ABSOLUTE_PATH",                       "description": "short desc"}
  ]
}

RULES:
1. Valid ops: mkdir · write_file · run_cmd · delete_file
2. Relative paths are resolved relative to: {workdir}
3. write_file content = COMPLETE file exactly as it should appear on disk, never truncated.
4. run_cmd uses Windows shell. Python = py -3.11, Pip = pip install ... --quiet
5. mkdir parent dirs BEFORE write_file steps inside them.
6. If no path is specified in the task, put everything under {workdir}.
7. Order: create dirs → write files → install deps → build/compile.
8. Your ENTIRE response must be parseable by json.loads(). Nothing else."""


def _plan_task(text: str, gemini_url: str, message_cb) -> dict | None:
    message_cb('system', '🧠 AGENT: Sending task to Gemini for planning...')
    system = _PLANNER_SYSTEM.replace('{workdir}', DEFAULT_WORKDIR)
    payload = {
        'system_instruction': {'parts': [{'text': system}]},
        'contents':           [{'role': 'user', 'parts': [{'text': text}]}],
        'generationConfig':   {'temperature': 0.1, 'maxOutputTokens': PLAN_TOKEN_LIMIT},
    }
    try:
        r    = requests.post(gemini_url, json=payload, timeout=PLAN_TIMEOUT)
        data = r.json()
        if 'candidates' not in data:
            err = data.get('error', {}).get('message', 'Unknown Gemini error')
            message_cb('system', f'❌ AGENT: Gemini error — {err}')
            return None
        raw = data['candidates'][0]['content']['parts'][0]['text'].strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.IGNORECASE)
        raw = re.sub(r'\s*```$', '', raw).strip()
        plan = json.loads(raw)
        message_cb('system', f'✅ AGENT: Plan received — {len(plan.get("steps", []))} step(s).')
        return plan
    except json.JSONDecodeError as e:
        message_cb('system', f'❌ AGENT: Could not parse plan as JSON — {e}')
        return None
    except requests.exceptions.Timeout:
        message_cb('system', '❌ AGENT: Gemini planning timed out.')
        return None
    except Exception as e:
        message_cb('system', f'❌ AGENT: Planning exception — {e}')
        return None


# ── Execution ───────────────────────────────────────────────────────────────

def _execute_plan(steps, update_ui_cb, speak_cb, message_cb):
    total = len(steps)
    for i, step in enumerate(steps, 1):
        op   = step.get('op', '').lower().strip()
        desc = step.get('description', op)
        update_ui_cb('setAgentMode', f'STEP {i}/{total}: {desc}')
        message_cb('system', f'⚙ [{i}/{total}] {desc}')
        try:
            if   op == 'mkdir':       _exec_mkdir(step, message_cb)
            elif op == 'write_file':  _exec_write_file(step, message_cb)
            elif op == 'run_cmd':     _exec_run_cmd(step, message_cb)
            elif op == 'delete_file': _exec_delete_file(step, message_cb)
            else: message_cb('system', f'⚠ AGENT: Unknown op "{op}" — skipped.')
        except Exception as e:
            message_cb('system', f'❌ AGENT: Step {i} exception — {e}')


def _resolve(path: str) -> str:
    path = path.strip()
    path = os.path.expandvars(os.path.expanduser(path))
    if not os.path.isabs(path):
        path = os.path.join(DEFAULT_WORKDIR, path)
    return os.path.normpath(path)


def _exec_mkdir(step, message_cb):
    path = _resolve(step.get('path', ''))
    if not path: return
    os.makedirs(path, exist_ok=True)
    message_cb('system', f'📁 Created: {path}')


def _exec_write_file(step, message_cb):
    path    = _resolve(step.get('path', ''))
    content = step.get('content', '')
    if not path: return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(content)
    message_cb('system', f'📝 Written: {path} ({len(content):,} chars)')


def _exec_delete_file(step, message_cb):
    path = _resolve(step.get('path', ''))
    if not path or not os.path.exists(path):
        message_cb('system', f'⚠ AGENT: Not found, skipping delete: {path}')
        return
    if os.path.isdir(path): shutil.rmtree(path); message_cb('system', f'🗑 Deleted dir: {path}')
    else: os.remove(path); message_cb('system', f'🗑 Deleted: {path}')


def _exec_run_cmd(step, message_cb):
    cmd = step.get('cmd', '').strip()
    cwd = step.get('cwd', DEFAULT_WORKDIR)
    if not cmd: return
    if cwd:
        cwd = _resolve(cwd)
        os.makedirs(cwd, exist_ok=True)
    message_cb('system', f'▶ CMD: {cmd}')
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd or None,
                                capture_output=True, text=True,
                                timeout=CMD_TIMEOUT, encoding='utf-8', errors='replace')
        if result.returncode == 0:
            out = (result.stdout or '').strip()
            message_cb('system', f'✅ OK: {out[:300]}' if out else '✅ Command completed.')
        else:
            err = (result.stderr or result.stdout or '').strip()
            message_cb('system', f'⚠ Exit {result.returncode}: {err[:300]}')
    except subprocess.TimeoutExpired:
        message_cb('system', f'⚠ Timed out after {CMD_TIMEOUT}s: {cmd}')
    except Exception as e:
        message_cb('system', f'❌ CMD exception: {e}')


# ── Announcements ────────────────────────────────────────────────────────────

def _announce_start(update_ui_cb, speak_cb, message_cb):
    update_ui_cb('setAgentMode', 'true')
    message_cb('system', '🔒 AGENT MODE ACTIVATED — locked in. All input blocked until task completes.')
    speak_cb("Agent mode activated, sir. I'm locked in — I'll notify you when it's done.")


def _announce_done(task_summary, step_count, update_ui_cb, speak_cb, message_cb):
    msg = f'✅ TASK COMPLETE — {task_summary}. All {step_count} step(s) executed, sir.'
    message_cb('jarvis', msg)
    speak_cb(f"Task complete, sir. {task_summary}. All {step_count} steps executed successfully.")


def _fail(reason, update_ui_cb, speak_cb, message_cb):
    message_cb('system', f'❌ AGENT FAILED — {reason}')
    speak_cb(f"Agent task failed, sir. {reason}")
    update_ui_cb('setAgentMode', 'false')
