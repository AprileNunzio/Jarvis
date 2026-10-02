import datetime as dt
import re

MONTHS = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
          "ottobre", "novembre", "dicembre"]
DAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
FEASTS = {"natale": (12, 25), "vigilia": (12, 24), "santo stefano": (12, 26), "capodanno": (1, 1),
          "epifania": (1, 6), "befana": (1, 6), "san valentino": (2, 14), "festa della donna": (3, 8),
          "festa della liberazione": (4, 25), "festa dei lavoratori": (5, 1), "primo maggio": (5, 1),
          "festa della repubblica": (6, 2), "ferragosto": (8, 15), "halloween": (10, 31),
          "ognissanti": (11, 1), "immacolata": (12, 8), "san silvestro": (12, 31)}
DATE_RE = (r"(\d{1,2})\s*(?:/|-|\s)\s*(\d{1,2}|" + "|".join(MONTHS) + r")(?:\s*(?:/|-|\s)\s*(\d{2,4}))?")


def easter(year: int) -> dt.date:
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    lz = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * lz) // 451
    month = (h + lz - 7 * m + 114) // 31
    return dt.date(year, month, (h + lz - 7 * m + 114) % 31 + 1)


def say(d: dt.date) -> str:
    return f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]} {d.year}"


def parse_dates(t: str, today: dt.date) -> list:
    found = []
    for name, (mo, da) in FEASTS.items():
        for m in re.finditer(rf"\b{name}\b", t):
            found.append((m.start(), mo, da, None))
    for m in re.finditer(r"\bpasqua\b", t):
        e = easter(today.year) if easter(today.year) >= today else easter(today.year + 1)
        found.append((m.start(), e.month, e.day, e.year))
    for m in re.finditer(DATE_RE, t):
        mo = int(m.group(2)) if m.group(2).isdigit() else MONTHS.index(m.group(2)) + 1
        year = int(m.group(3)) if m.group(3) else None
        if year is not None and year < 100:
            year += 2000
        found.append((m.start(), mo, int(m.group(1)), year))
    out = []
    for _, mo, da, year in sorted(found):
        try:
            d = dt.date(year or today.year, mo, da)
        except ValueError:
            continue
        if year is None and d < today:
            d = d.replace(year=today.year + 1)
        out.append(d)
    return out


def run(text: str) -> dict:
    t = text.lower()
    today = dt.date.today()
    m = re.search(r"tra\s+(\d+)\s+(giorni|settimane|mesi)|(\d+)\s+(giorni|settimane|mesi)\s+fa", t)
    if m and re.search(r"che\s+(giorno|data)|quando", t):
        n = int(m.group(1) or m.group(3))
        unit = m.group(2) or m.group(4)
        days = n * {"giorni": 1, "settimane": 7, "mesi": 30}[unit]
        sign = -1 if m.group(3) else 1
        target = today + dt.timedelta(days=sign * days)
        speech = f"Tra {n} {unit} sarà {say(target)}." if sign > 0 else f"{n} {unit} fa era {say(target)}."
        return {"ok": True, "result": target.isoformat(), "speech": speech}
    dates = parse_dates(t, today)
    if not dates:
        return {"ok": False, "error": "nessuna data riconosciuta"}
    if len(dates) >= 2 and re.search(r"\btra\b|\bfra\b|\bdal\b|\bda\b", t):
        a, b = dates[0], dates[1]
        if b < a and not re.search(r"\d{4}", t):
            b = b.replace(year=b.year + 1)
        n = (b - a).days
        return {"ok": True, "result": n, "speech": f"Tra {say(a)} e {say(b)} ci sono {n} giorni."}
    target = dates[0]
    n = (target - today).days
    if n == 0:
        return {"ok": True, "result": 0, "speech": f"È oggi, {say(target)}!"}
    if n < 0:
        return {"ok": True, "result": n, "speech": f"Sono passati {-n} giorni da {say(target)}."}
    weeks = f", cioè {n // 7} settimane e {n % 7} giorni" if n > 13 else ""
    return {"ok": True, "result": n, "speech": f"Mancano {n} giorni a {say(target)}{weeks}."}
