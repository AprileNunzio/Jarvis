import json
import time
import uuid
from datetime import datetime, timedelta

from config import STATE_DIR, env_get
from state import store

from features.sounds.library import CATEGORY, URGENT, names

FILE = STATE_DIR / "sounds.json"
CUE_TTL = 8


def _int(key: str, default: int, low: int = 0, high: int = 100) -> int:
    try:
        return max(low, min(high, int(float(env_get(key, str(default))))))
    except ValueError:
        return default


def _hm(key: str, default: str) -> str:
    value = env_get(key, default).strip()
    try:
        datetime.strptime(value, "%H:%M")
        return value
    except ValueError:
        return default


class Policy:
    def __init__(self) -> None:
        self.cues: list[dict] = []
        try:
            self.manual = json.loads(FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.manual = {}

    def _save(self) -> None:
        FILE.write_text(json.dumps(self.manual), encoding="utf-8")

    def settings(self) -> dict:
        return {
            "enabled": env_get("JARVIS_SOUNDS", "1") != "0",
            "volume": _int("JARVIS_SOUNDS_VOLUME", 55),
            "theme": env_get("JARVIS_SOUNDS_THEME", "jarvis"),
            "feedback": env_get("JARVIS_SOUNDS_FEEDBACK", "1") != "0",
            "thinking": env_get("JARVIS_SOUNDS_THINKING", "1") != "0",
            "notify": env_get("JARVIS_SOUNDS_NOTIFY", "1") != "0",
            "ambient": env_get("JARVIS_SOUNDS_AMBIENT", "none"),
            "ambient_volume": _int("JARVIS_SOUNDS_AMBIENT_VOLUME", 18),
            "quiet_mode": env_get("JARVIS_QUIET_MODE", "soft"),
            "quiet_start": _hm("JARVIS_QUIET_START", "23:00"),
            "quiet_end": _hm("JARVIS_QUIET_END", "07:00"),
            "quiet_days": env_get("JARVIS_QUIET_DAYS", "all"),
            "quiet_voice": _int("JARVIS_QUIET_VOICE", 45),
            "quiet_effects": _int("JARVIS_QUIET_EFFECTS", 25),
        }

    def scheduled(self, now: datetime | None = None) -> bool:
        s = self.settings()
        if s["quiet_mode"] == "off":
            return False
        now = now or datetime.now()
        start, end = s["quiet_start"], s["quiet_end"]
        cur = now.strftime("%H:%M")
        inside = start <= cur < end if start <= end else cur >= start or cur < end
        if not inside:
            return False
        anchor = now if start <= end or cur >= start else now - timedelta(days=1)
        days = s["quiet_days"]
        if days == "weekdays":
            return anchor.weekday() in (6, 0, 1, 2, 3)
        if days == "weekend":
            return anchor.weekday() in (4, 5)
        return True

    def dnd(self) -> dict | None:
        m = self.manual.get("dnd")
        if not m:
            return None
        if m.get("until") and time.time() > m["until"]:
            self.manual.pop("dnd", None)
            self._save()
            return None
        return m

    def quiet(self) -> bool:
        return bool(self.dnd()) or (self.scheduled() and self.manual.get("override_until", 0) <= time.time())

    def set_dnd(self, minutes: float | None, reason: str = "manuale") -> str:
        until = time.time() + minutes * 60 if minutes else None
        self.manual["dnd"] = {"since": time.time(), "until": until, "reason": reason}
        self._save()
        store.touch()
        if until:
            return f"Non disturbare attivo fino alle {datetime.fromtimestamp(until):%H:%M}"
        return "Non disturbare attivo finché non lo disattiva"

    def clear_dnd(self) -> str:
        self.manual.pop("dnd", None)
        self.manual["override_until"] = time.time() + 3600 if self.scheduled() else 0
        self._save()
        store.touch()
        return "Suoni riattivati"

    def state(self) -> dict:
        s = self.settings()
        dnd = self.dnd()
        quiet = self.quiet()
        level = "mute" if dnd else (s["quiet_mode"] if quiet else "")
        now = time.time()
        self.cues = [c for c in self.cues if now - c["at"] < CUE_TTL]
        return {**s, "quiet": quiet, "level": level, "dnd": dnd, "cues": self.cues}

    def play(self, name: str, force: bool = False, reason: str = "") -> str:
        if name not in names():
            raise ValueError(f"suono sconosciuto «{name}»")
        st = self.state()
        if not st["enabled"] and not force:
            return "suoni disattivati"
        if st["quiet"] and not force and name not in URGENT:
            return "non suonato: silenzio"
        self.cues.append({"id": uuid.uuid4().hex[:8], "name": name, "at": time.time(), "force": force,
                          "category": CATEGORY.get(name, "effetti"), "reason": reason[:80]})
        store.touch()
        return f"suono «{name}» riprodotto"


policy = Policy()
