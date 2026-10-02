import re

NUM = r"(\d{1,3}(?:\.\d{3})+|\d+(?:[.,]\d+)?)"


def num(s: str) -> float:
    s = s.strip()
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s):
        s = s.replace(".", "")
    return float(s.replace(",", "."))


def euro(v: float) -> str:
    return f"{v:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def run(text: str) -> dict:
    t = text.lower().replace("€", " euro ")
    t = re.sub(r"(\d)\s*(mila|k)\b", lambda m: m.group(1) + "000", t)
    rate_m = re.search(NUM + r"\s*(?:%|per\s*cento)", t)
    years_m = re.search(NUM + r"\s*(anni|anno|mesi|mese)\b", t)
    if not rate_m or not years_m:
        return {"ok": False, "error": "servono tasso e durata"}
    rest = t[:rate_m.start()] + " " + t[rate_m.end():years_m.start()] + " " + t[years_m.end():]
    cap_m = re.search(NUM + r"\s*(?:euro|eur|dollari|\$)", rest) or re.search(NUM, rest)
    if not cap_m:
        return {"ok": False, "error": "manca il capitale"}
    capital, rate = num(cap_m.group(1)), num(rate_m.group(1)) / 100
    years = num(years_m.group(1)) / (12 if years_m.group(2).startswith("mes") else 1)
    if capital <= 0 or not 0 < rate < 1 or not 0 < years <= 200:
        return {"ok": False, "error": "valori fuori scala"}
    per_year = 12 if re.search(r"\bmensil\w*|ogni mese\b", t) and not re.search(r"(tasso|interesse)\s+mensile", t) else \
        4 if re.search(r"trimestral\w*", t) else 1
    if "semplice" in t:
        final = capital * (1 + rate * years)
        kind = "semplice"
    else:
        final = capital * (1 + rate / per_year) ** (per_year * years)
        kind = "composto" + (" con capitalizzazione mensile" if per_year == 12 else " trimestrale" if per_year == 4 else "")
    gain = final - capital
    y = f"{years:g}".replace(".", ",")
    return {"ok": True, "result": round(final, 2),
            "speech": f"Con {euro(capital)} euro al {f'{rate * 100:g}'.replace('.', ',')}% di interesse {kind}, "
                      f"dopo {y} anni avrai {euro(final)} euro, cioè {euro(gain)} euro di interessi."}
