import json
import re
import time
import uuid
from datetime import datetime, timedelta

from config import STATE_DIR

FILE = STATE_DIR / "routines.json"
DAYS = {"lunedi": 0, "martedi": 1, "mercoledi": 2, "giovedi": 3, "venerdi": 4, "sabato": 5, "domenica": 6}
DAY_NAMES = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
PARTS = {"mattina": "08:00", "mattino": "08:00", "pomeriggio": "15:00", "sera": "20:00", "notte": "23:00", "mezzogiorno": "12:00"}
EVENTS = {"arrival": "quando mi vedi arrivare", "startup": "all'avvio di Jarvis"}


def _load() -> list[dict]:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save(items: list[dict]) -> None:
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(FILE)


def _hhmm(text: str) -> str | None:
    m = re.search(r"\b(?:alle|ore|all')\s*(\d{1,2})(?:[:.](\d{2}))?\b", text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        if "sera" in text and h < 12 or "pomeriggio" in text and h < 12:
            h += 12
        return f"{h % 24:02d}:{mi:02d}" if mi < 60 else None
    for word, value in PARTS.items():
        if word in text:
            return value
    return None


def parse_when(text: str) -> dict:
    t = text.lower().replace("ì", "i").replace("è", "e")
    m = re.search(r"\bogni\s+(\d+)\s*(minut|or[ae])", t)
    if m:
        n = int(m.group(1)) * (60 if m.group(2).startswith("or") else 1)
        return {"type": "every", "minutes": max(5, min(n, 7 * 24 * 60))}
    if re.search(r"\bogni\s+ora\b", t):
        return {"type": "every", "minutes": 60}
    m = re.search(r"\btra\s+(\d+)\s*(minut|or[ae]|giorn)", t)
    if m:
        g = m.group(2)
        unit = 60 if g.startswith("minut") else 3600 if g.startswith("or") else 86400
        return {"type": "once", "at": time.time() + int(m.group(1)) * unit}
    if re.search(r"quando (mi )?vedi|quando arrivo|quando torno", t):
        return {"type": "event", "on": "arrival"}
    if re.search(r"all'?avvio|quando ti accendi", t):
        return {"type": "event", "on": "startup"}
    at = _hhmm(t) or "08:00"
    days = sorted({d for name, d in DAYS.items() if re.search(rf"\b{name}", t)})
    if re.search(r"\b(giorni feriali|dal lunedi al venerdi|in settimana)\b", t):
        days = [0, 1, 2, 3, 4]
    if re.search(r"\b(weekend|fine settimana)\b", t):
        days = [5, 6]
    if re.search(r"\bdomani\b", t) and not re.search(r"\bogni\b", t):
        h, mi = map(int, at.split(":"))
        when = (datetime.now() + timedelta(days=1)).replace(hour=h, minute=mi, second=0, microsecond=0)
        return {"type": "once", "at": when.timestamp()}
    if re.search(r"\boggi\b|\bstasera\b", t) and not re.search(r"\bogni\b", t):
        h, mi = map(int, at.split(":"))
        when = datetime.now().replace(hour=h, minute=mi, second=0, microsecond=0)
        return {"type": "once", "at": when.timestamp() if when.timestamp() > time.time() else time.time() + 60}
    return {"type": "daily", "time": at, "days": days or list(range(7))}


def describe(when: dict) -> str:
    kind = when.get("type")
    if kind == "every":
        m = when["minutes"]
        return f"ogni {m // 60} ore" if m % 60 == 0 and m >= 120 else "ogni ora" if m == 60 else f"ogni {m} minuti"
    if kind == "once":
        return "una volta, " + datetime.fromtimestamp(when["at"]).strftime("%d/%m alle %H:%M")
    if kind == "event":
        return EVENTS.get(when.get("on"), when.get("on", ""))
    days = when.get("days") or list(range(7))
    which = "ogni giorno" if len(days) == 7 else "nei giorni feriali" if days == [0, 1, 2, 3, 4] else \
        "nel fine settimana" if days == [5, 6] else "ogni " + ", ".join(DAY_NAMES[d] for d in days)
    return f"{which} alle {when.get('time', '08:00')}"


def due(r: dict, now: float) -> bool:
    if not r.get("enabled", True):
        return False
    when, last = r.get("when") or {}, r.get("last_run", 0)
    kind = when.get("type")
    if kind == "every":
        return now - last >= when["minutes"] * 60
    if kind == "once":
        return not last and now >= when.get("at", 0)
    if kind != "daily":
        return False
    dt = datetime.fromtimestamp(now)
    h, mi = map(int, when.get("time", "08:00").split(":"))
    slot = dt.replace(hour=h, minute=mi, second=0, microsecond=0)
    return dt.weekday() in (when.get("days") or range(7)) and slot <= dt < slot + timedelta(minutes=30) and last < slot.timestamp()


class Routines:
    def all(self) -> list[dict]:
        return _load()

    def get(self, rid: str) -> dict:
        found = next((r for r in _load() if r["id"] == rid), None)
        if not found:
            raise KeyError(rid)
        return found

    def add(self, title: str, prompt: str, when: dict, origin: str = "voce") -> dict:
        item = {"id": uuid.uuid4().hex[:8], "title": title[:80] or prompt[:60], "prompt": prompt[:1000], "when": when,
                "enabled": True, "created": time.time(), "origin": origin, "last_run": 0, "last_result": "", "runs": 0}
        items = _load()
        items.append(item)
        _save(items[-100:])
        return item

    def update(self, rid: str, **changes) -> dict:
        items = _load()
        for r in items:
            if r["id"] == rid:
                r.update({k: v for k, v in changes.items() if k in ("title", "prompt", "when", "enabled", "last_run",
                                                                      "last_result", "runs", "trusted")})
                _save(items)
                return r
        raise KeyError(rid)

    def remove(self, rid: str) -> None:
        items = [r for r in _load() if r["id"] != rid]
        _save(items)

    def due_now(self, now: float | None = None) -> list[dict]:
        now = now or time.time()
        return [r for r in _load() if due(r, now)]

    def for_event(self, event: str) -> list[dict]:
        return [r for r in _load() if r.get("enabled", True) and (r.get("when") or {}).get("type") == "event"
                and r["when"].get("on") == event]


routines = Routines()
