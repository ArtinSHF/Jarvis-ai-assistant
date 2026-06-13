"""
reminder_engine.py — reminders, timers, recurring reminders, daily briefing with news
"""
import threading
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

_reminders  = []  # {time, message, recurring}
_lock       = threading.Lock()
_callback   = None
_briefing_hour   = 8
_briefing_minute = 0
_briefing_done_date = None


def set_callback(fn):
    global _callback
    _callback = fn


def set_briefing_time(hour, minute):
    global _briefing_hour, _briefing_minute
    _briefing_hour   = hour
    _briefing_minute = minute


def add_timer(label, seconds):
    fire_at = datetime.now() + timedelta(seconds=seconds)
    with _lock:
        _reminders.append({'time': fire_at, 'message': label, 'recurring': None})
    return fire_at.strftime('%I:%M %p')


def add_reminder(message, at_time_str, recurring=None):
    """
    recurring: None | 'daily' | 'weekdays' | 'weekends'
    """
    try:
        h, m = map(int, at_time_str.split(':'))
        fire_at = datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
        if fire_at <= datetime.now():
            fire_at += timedelta(days=1)
        with _lock:
            _reminders.append({'time': fire_at, 'message': message, 'recurring': recurring})
        label = f"{'Recurring ' if recurring else ''}{fire_at.strftime('%I:%M %p')}"
        return label
    except Exception:
        return None


def list_reminders():
    now = datetime.now()
    with _lock:
        return [r for r in _reminders if r['time'] > now]


def get_weather():
    try:
        r = requests.get('https://wttr.in/Hillerod?format=3', timeout=5)
        return r.text.strip() if r.status_code == 200 else 'weather unavailable'
    except Exception:
        return 'weather unavailable'


def get_top_news():
    try:
        r    = requests.get('https://feeds.bbci.co.uk/news/rss.xml', timeout=6)
        root = ET.fromstring(r.content)
        items = root.findall('./channel/item')[:3]
        return [item.find('title').text for item in items if item.find('title') is not None]
    except Exception:
        return []


def get_briefing():
    now      = datetime.now()
    weather  = get_weather()
    headlines = get_top_news()
    upcoming  = list_reminders()

    reminder_info = (
        f"You have {len(upcoming)} reminder{'s' if len(upcoming)>1 else ''} today. "
        f"Next: {min(upcoming,key=lambda x:x['time'])['message']} "
        f"at {min(upcoming,key=lambda x:x['time'])['time'].strftime('%I:%M %p')}."
        if upcoming else "No reminders scheduled today."
    )

    news_part = (
        f"Top headlines: {'. '.join(headlines[:3])}."
        if headlines else "News feed unavailable."
    )

    return (
        f"Good morning, sir. Today is {now.strftime('%A, %B %d')}. "
        f"The time is {now.strftime('%I:%M %p')}. "
        f"Conditions in Hillerød: {weather}. "
        f"{reminder_info} {news_part} "
        f"All systems nominal. Ready for your orders."
    )


def _next_occurrence(r, now):
    """Calculate next fire time for a recurring reminder."""
    t = r['time']
    recurring = r['recurring']
    if recurring == 'daily':
        while t <= now:
            t += timedelta(days=1)
    elif recurring == 'weekdays':
        while t <= now or t.weekday() >= 5:
            t += timedelta(days=1)
    elif recurring == 'weekends':
        while t <= now or t.weekday() < 5:
            t += timedelta(days=1)
    return t


def _engine():
    global _briefing_done_date
    while True:
        now = datetime.now()

        # Daily briefing
        if (now.hour == _briefing_hour and now.minute == _briefing_minute
                and now.date() != _briefing_done_date):
            _briefing_done_date = now.date()
            if _callback:
                threading.Thread(target=_callback, args=(get_briefing(),), daemon=True).start()

        # Fire reminders
        fired = []
        with _lock:
            for r in list(_reminders):
                if now >= r['time']:
                    fired.append(r)
                    _reminders.remove(r)

        for r in fired:
            if _callback:
                msg = f"Reminder, sir: {r['message']}"
                threading.Thread(target=_callback, args=(msg,), daemon=True).start()
            # Re-queue if recurring
            if r.get('recurring'):
                next_t = _next_occurrence(r, now)
                new_r  = dict(r)
                new_r['time'] = next_t
                with _lock:
                    _reminders.append(new_r)

        time.sleep(1)


def start():
    threading.Thread(target=_engine, daemon=True).start()
