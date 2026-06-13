"""
notes.py — Simple JSON-based note system for JARVIS
"""
import json
import os
from datetime import datetime

NOTES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jarvis_notes.json')


def _load():
    if not os.path.exists(NOTES_FILE):
        return []
    try:
        with open(NOTES_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return []


def _save(notes):
    with open(NOTES_FILE, 'w') as f:
        json.dump(notes, f, indent=2)


def add_note(text):
    notes = _load()
    notes.append({
        'text': text.strip(),
        'time': datetime.now().strftime('%Y-%m-%d %H:%M')
    })
    _save(notes)
    return len(notes)


def get_notes():
    return _load()


def clear_notes():
    _save([])


def delete_note(index):
    notes = _load()
    if 0 <= index < len(notes):
        removed = notes.pop(index)
        _save(notes)
        return removed['text']
    return None


def read_notes_aloud():
    notes = _load()
    if not notes:
        return "You have no notes, sir."
    if len(notes) == 1:
        return f"You have 1 note: {notes[0]['text']}"
    lines = [f"You have {len(notes)} notes, sir."]
    for i, n in enumerate(notes[-5:], 1):  # read last 5
        lines.append(f"Note {i}: {n['text']}")
    return ' '.join(lines)
