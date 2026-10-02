import logging

from config import STATE_DIR

log = logging.getLogger("jarvis.google")

REDIRECT_URI = "http://127.0.0.1:8889/"
STATE_FILE = STATE_DIR / "google.json"
SERVICES = {
    "calendar": {"name": "Google Calendar", "icon": "📅", "api": "calendar-json.googleapis.com",
                 "scopes": ["https://www.googleapis.com/auth/calendar.readonly",
                            "https://www.googleapis.com/auth/calendar.events"]},
    "gmail": {"name": "Gmail", "icon": "✉️", "api": "gmail.googleapis.com",
              "scopes": ["https://www.googleapis.com/auth/gmail.readonly"]},
    "gmail_send": {"name": "Invio email", "icon": "📤", "api": "gmail.googleapis.com",
                   "scopes": ["https://www.googleapis.com/auth/gmail.send"]},
    "tasks": {"name": "Google Tasks", "icon": "✅", "api": "tasks.googleapis.com",
              "scopes": ["https://www.googleapis.com/auth/tasks"]},
    "contacts": {"name": "Contatti", "icon": "👥", "api": "people.googleapis.com",
                 "scopes": ["https://www.googleapis.com/auth/contacts.readonly"]},
    "drive": {"name": "Google Drive", "icon": "📁", "api": "drive.googleapis.com",
              "scopes": ["https://www.googleapis.com/auth/drive.metadata.readonly"]},
    "keep": {"name": "Google Keep", "icon": "📝", "api": "keep.googleapis.com", "workspace": True,
             "scopes": ["https://www.googleapis.com/auth/keep"]},
}
DEFAULT_SERVICES = "calendar,gmail,gmail_send,tasks,contacts,drive"
DAYS_IT = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MONTHS_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
             "ottobre", "novembre", "dicembre"]


class NotLinked(Exception):
    pass
