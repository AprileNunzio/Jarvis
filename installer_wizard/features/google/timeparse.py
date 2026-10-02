import re
from datetime import date, timedelta

from features.google.constants import DAYS_IT, MONTHS_IT

_NUM = {"una": 1, "un": 1, "uno": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5, "sei": 6, "sette": 7, "otto": 8,
        "nove": 9, "dieci": 10, "undici": 11, "dodici": 12, "tredici": 13, "quattordici": 14, "quindici": 15,
        "sedici": 16, "diciassette": 17, "diciotto": 18, "diciannove": 19, "venti": 20, "ventuno": 21,
        "ventidue": 22, "ventitré": 23, "ventitre": 23, "mezzogiorno": 12, "mezzanotte": 0}
_DAY_RE = re.compile(r"\b(oggi|stamattina|stasera|stanotte|stamani|domani|dopodomani|"
                     r"(?:(?:questo|questa|prossimo|prossima)\s+)?(lunedì|lunedi|martedì|martedi|mercoledì|mercoledi|"
                     r"giovedì|giovedi|venerdì|venerdi|sabato|domenica)(?:\s+prossim[oa])?|"
                     r"(?:il\s+|l')?(\d{1,2})(?:\s+|/)(" + "|".join(MONTHS_IT) + r"|\d{1,2})(?:(?:\s+|/)(\d{4}))?)\b", re.I)
_TIME_RE = re.compile(r"\b(?:alle|all'|per le|verso le|dalle|ore)\s*(?:ore\s+)?(\d{1,2}|" + "|".join(_NUM) + r")"
                      r"(?:(?:[:.]|\s+e\s+)(\d{2}|mezza|mezzo|un quarto|quarto|trenta|quindici|quaranta|"
                      r"quarantacinque|dieci|venti))?"
                      r"(?:\s+(del mattino|di mattina|della mattina|del pomeriggio|di pomeriggio|di sera|della sera|"
                      r"di notte|della notte))?\b", re.I)
_DUR_RE = re.compile(r"\bper\s+(\d+|un'?|una|mezz'?|due|tre|quattro)\s*(ora|ore|minuti|mezz'?ora)\b", re.I)
_MIN = {"mezza": 30, "mezzo": 30, "un quarto": 15, "quarto": 15, "trenta": 30, "quindici": 15, "quaranta": 40,
        "quarantacinque": 45, "dieci": 10, "venti": 20}


def parse_day(text: str, today: date | None = None) -> tuple[date | None, re.Match | None]:
    today = today or date.today()
    m = _DAY_RE.search(text)
    if not m:
        return None, None
    w = m.group(1).lower()
    if w.startswith(("oggi", "stamattina", "stasera", "stanotte", "stamani")):
        return today, m
    if w == "domani":
        return today + timedelta(days=1), m
    if w == "dopodomani":
        return today + timedelta(days=2), m
    if m.group(2):
        idx = next(i for i, d in enumerate(DAYS_IT) if d.rstrip("ì") == m.group(2).lower().rstrip("ìi") or
                   d == m.group(2).lower())
        delta = (idx - today.weekday()) % 7
        if delta == 0 and "prossim" in w:
            delta = 7
        return today + timedelta(days=delta), m
    day = int(m.group(3))
    month = MONTHS_IT.index(m.group(4).lower()) + 1 if not m.group(4).isdigit() else int(m.group(4))
    year = int(m.group(5)) if m.group(5) else today.year
    try:
        d = date(year, month, day)
    except ValueError:
        return None, None
    if d < today and not m.group(5):
        d = date(year + 1, month, day)
    return d, m


def parse_time(text: str, assume_pm: bool = True) -> tuple[tuple[int, int] | None, re.Match | None]:
    m = _TIME_RE.search(text)
    if not m:
        return None, None
    h = int(m.group(1)) if m.group(1).isdigit() else _NUM.get(m.group(1).lower(), 0)
    mins = m.group(2) or ""
    minute = int(mins) if mins.isdigit() else _MIN.get(mins.lower(), 0)
    part = (m.group(3) or "").lower()
    evening = "sera" in part or "pomeriggio" in part or "stasera" in text.lower()
    if evening and h < 12:
        h += 12
    elif assume_pm and not part and 1 <= h <= 7 and "mattin" not in text.lower():
        h += 12
    if not (0 <= h <= 23 and 0 <= minute <= 59):
        return None, None
    return (h, minute), m


def parse_duration(text: str) -> tuple[int | None, re.Match | None]:
    m = _DUR_RE.search(text)
    if not m:
        return None, None
    n, unit = m.group(1).lower(), m.group(2).lower()
    if unit.startswith("mezz") or n.startswith("mezz"):
        return 30, m
    qty = int(n) if n.isdigit() else _NUM.get(n.rstrip("'"), 1)
    return (qty * 60 if unit.startswith("or") else qty), m


def strip_phrase(text: str, *matches) -> str:
    for m in sorted([m for m in matches if m], key=lambda m: -m.start()):
        text = text[:m.start()] + " " + text[m.end():]
    return re.sub(r"\s{2,}", " ", text).strip(" ,.;:!?")


def say_day(d: date, today: date | None = None) -> str:
    today = today or date.today()
    if d == today:
        return "oggi"
    if d == today + timedelta(days=1):
        return "domani"
    if 0 < (d - today).days < 7:
        return DAYS_IT[d.weekday()]
    return f"{DAYS_IT[d.weekday()]} {d.day} {MONTHS_IT[d.month - 1]}"


def event_json(e: dict) -> dict:
    return {**e, "start": e["start"].isoformat(), "when": ("tutto il giorno" if e["all_day"]
                                                          else e["start"].strftime("%H:%M")),
            "day": say_day(e["start"].date())}
