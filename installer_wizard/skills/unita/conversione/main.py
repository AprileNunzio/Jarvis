import re

UNITS = {
    "mm": ("lunghezza", 0.001), "millimetri": ("lunghezza", 0.001), "millimetro": ("lunghezza", 0.001),
    "cm": ("lunghezza", 0.01), "centimetri": ("lunghezza", 0.01), "centimetro": ("lunghezza", 0.01),
    "m": ("lunghezza", 1.0), "metri": ("lunghezza", 1.0), "metro": ("lunghezza", 1.0),
    "km": ("lunghezza", 1000.0), "chilometri": ("lunghezza", 1000.0), "chilometro": ("lunghezza", 1000.0),
    "pollici": ("lunghezza", 0.0254), "pollice": ("lunghezza", 0.0254),
    "piedi": ("lunghezza", 0.3048), "piede": ("lunghezza", 0.3048),
    "iarde": ("lunghezza", 0.9144), "iarda": ("lunghezza", 0.9144),
    "miglia": ("lunghezza", 1609.344), "miglio": ("lunghezza", 1609.344),
    "miglia nautiche": ("lunghezza", 1852.0),
    "mg": ("massa", 0.001), "milligrammi": ("massa", 0.001), "g": ("massa", 1.0), "grammi": ("massa", 1.0),
    "grammo": ("massa", 1.0), "etti": ("massa", 100.0), "etto": ("massa", 100.0), "kg": ("massa", 1000.0),
    "chili": ("massa", 1000.0), "chilo": ("massa", 1000.0), "chilogrammi": ("massa", 1000.0),
    "quintali": ("massa", 100000.0), "tonnellate": ("massa", 1e6), "tonnellata": ("massa", 1e6),
    "libbre": ("massa", 453.59237), "libbra": ("massa", 453.59237), "once": ("massa", 28.349523125), "oncia": ("massa", 28.349523125),
    "ml": ("volume", 0.001), "millilitri": ("volume", 0.001), "cl": ("volume", 0.01), "centilitri": ("volume", 0.01),
    "dl": ("volume", 0.1), "decilitri": ("volume", 0.1), "l": ("volume", 1.0), "litri": ("volume", 1.0),
    "litro": ("volume", 1.0), "galloni": ("volume", 3.785411784), "gallone": ("volume", 3.785411784),
    "metri cubi": ("volume", 1000.0), "tazze": ("volume", 0.24), "tazza": ("volume", 0.24),
    "km/h": ("velocità", 1 / 3.6), "chilometri orari": ("velocità", 1 / 3.6), "chilometri all'ora": ("velocità", 1 / 3.6),
    "m/s": ("velocità", 1.0), "metri al secondo": ("velocità", 1.0), "mph": ("velocità", 0.44704),
    "miglia orarie": ("velocità", 0.44704), "nodi": ("velocità", 0.514444),
    "metri quadri": ("superficie", 1.0), "metri quadrati": ("superficie", 1.0), "mq": ("superficie", 1.0),
    "ettari": ("superficie", 10000.0), "ettaro": ("superficie", 10000.0), "km quadrati": ("superficie", 1e6),
    "acri": ("superficie", 4046.8564224),
    "byte": ("dati", 1.0), "kb": ("dati", 1e3), "mb": ("dati", 1e6), "gb": ("dati", 1e9), "tb": ("dati", 1e12),
    "kib": ("dati", 1024.0), "mib": ("dati", 1024.0 ** 2), "gib": ("dati", 1024.0 ** 3),
}
TEMPS = {"celsius": "C", "gradi celsius": "C", "°c": "C", "gradi": "C", "fahrenheit": "F", "gradi fahrenheit": "F",
         "°f": "F", "kelvin": "K"}
NAMES = sorted(list(UNITS) + list(TEMPS), key=len, reverse=True)
UNIT_RE = "|".join(re.escape(n) for n in NAMES)


def fmt(v: float) -> str:
    if abs(v) >= 1e9 or (v and abs(v) < 1e-4):
        return f"{v:.4g}".replace(".", ",")
    return f"{round(v, 4):f}".rstrip("0").rstrip(".").replace(".", ",")


def temp(v: float, a: str, b: str) -> float:
    c = v if a == "C" else (v - 32) * 5 / 9 if a == "F" else v - 273.15
    return c if b == "C" else c * 9 / 5 + 32 if b == "F" else c + 273.15


def run(text: str) -> dict:
    t = " " + text.lower().replace(",", ".") + " "
    m = re.search(rf"(-?\d+(?:\.\d+)?)\s*({UNIT_RE})\b.*?\b(?:in|a|come|quanti|quante|sono)\s+({UNIT_RE})\b", t) \
        or re.search(rf"quant[ie]\s+({UNIT_RE})\s+(?:sono|fanno|ci sono in|in)\s+(-?\d+(?:\.\d+)?)\s*({UNIT_RE})\b", t)
    if not m:
        return {"ok": False, "error": "unità non riconosciute"}
    if m.re.pattern.startswith("quant"):
        target, value, source = m.group(1), float(m.group(2)), m.group(3)
    else:
        value, source, target = float(m.group(1)), m.group(2), m.group(3)
    if source in TEMPS and target in TEMPS:
        out = temp(value, TEMPS[source], TEMPS[target])
    elif source in UNITS and target in UNITS and UNITS[source][0] == UNITS[target][0]:
        out = value * UNITS[source][1] / UNITS[target][1]
    else:
        return {"ok": False, "error": f"non posso convertire {source} in {target}"}
    return {"ok": True, "result": out, "speech": f"{fmt(value)} {source} sono {fmt(out)} {target}."}
