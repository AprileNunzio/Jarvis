import re
import unicodedata

from features.desktop.desk import desk
from features.desktop.screens import screens

MOVE = re.compile(r"\b(sposta|porta|manda|metti|trasferisci|lancia)\b(?P<what>.*?)\b(sul|sullo|nel|nello|all'|allo|al|in|verso)\s*"
                  r"(?P<where>(l'|lo |il )?(altro|secondo|terzo|quarto|primo|principale|ultimo)?\s*(schermo|monitor|display)"
                  r"(\s+(\d|principale|secondario))?)", re.I)
RESET = re.compile(r"\b(riporta|rimetti|sposta)\b.*\b(tutto|tutti i widget|i widget)\b.*\b(principale|primo schermo|qui)\b", re.I)
STOP = {"il", "la", "lo", "le", "gli", "di", "del", "della", "su", "un", "una", "widget", "finestra", "questo", "quello"}
ORDINALS = {"primo": 0, "principale": 0, "secondo": 1, "terzo": 2, "quarto": 3}


def _plain(text: str) -> str:
    return unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()


def _target(where: str, current: int | None) -> int | None:
    nums = screens.numbers()
    w = _plain(where)
    digit = re.search(r"\d", w)
    if digit:
        idx = int(digit.group()) - 1
        return nums[idx] if 0 <= idx < len(nums) else None
    for word, idx in ORDINALS.items():
        if word in w:
            return nums[idx] if idx < len(nums) else None
    if "ultimo" in w:
        return nums[-1]
    others = [n for n in nums if n != (current if current is not None else 0)]
    return others[0] if others else None


def _widget(what: str) -> dict | None:
    words = [x for x in re.findall(r"[a-z0-9]+", _plain(what)) if len(x) >= 2 and x not in STOP]
    active = {i["id"]: i for i in desk.active()}
    best, score = None, 0
    for m in desk.widgets.values():
        hay = _plain(f"{m['id']} {m['name']} {m.get('description', '')}")
        s = sum(2 if w in _plain(m["name"]) else 1 for w in words if w in hay) + (1 if m["id"] in active else 0)
        if s > score and (words or m["id"] in active):
            best, score = m, s
    if not words and active:
        top = desk.active()[0]
        return desk.widgets.get(top["id"])
    return best if score > (1 if words else 0) else None


async def answer(text: str) -> tuple[str, dict]:
    if RESET.search(text):
        for wid, rec in desk.prefs.items():
            rec.pop("screen", None)
        desk._save()
        desk.publish()
        return "Fatto: ho riportato i widget nella disposizione automatica.", {"mode": "face"}
    m = MOVE.search(text)
    if not m:
        raise LookupError
    if len(screens.numbers()) < 2:
        return "C'è un solo schermo collegato: collega un altro monitor e ci penso io.", {"mode": "face"}
    widget = _widget(m.group("what"))
    if not widget:
        return "Non ho capito quale widget spostare: dimmi il suo nome, per esempio «sposta il meteo sull'altro schermo».", {"mode": "face"}
    current = next((i.get("screen") for i in desk.active() if i["id"] == widget["id"]), None)
    target = _target(m.group("where"), current)
    if target is None:
        return "Quello schermo non è collegato in questo momento.", {"mode": "face"}
    desk.set_screen(widget["id"], target)
    return f"Ecco, {widget['name']} è sullo schermo {screens.numbers().index(target) + 1}.", {"mode": "face"}
