import re

DURABLE = [
    ("preferenza", re.compile(r"\b(?:mi piace(?:\s+molto)?|adoro|amo|preferisco|odio|non (?:mi piace|sopporto))\b.{2,120}", re.I)),
    ("preferenza", re.compile(r"\b(?:il mio|la mia)\s+(?:preferit[oa]|favorit[oa])\b.{2,120}", re.I)),
    ("fatto", re.compile(r"\b(?:ricorda(?:ti)?|tieni a mente|non dimenticare)\s+che\s+(.{3,160})", re.I)),
    ("identita", re.compile(r"\b(?:mi chiamo|il mio nome (?:è|e'))\s+([A-Za-zÀ-ÿ'’\- ]{2,40}?)"
                            r"(?=\s+(?:e|ed|,|\.|ma|abito|vivo|ho|sono|lavoro)\b|[.,;!?]|$)", re.I)),
    ("identita", re.compile(r"\b(?:ho|compio)\s+\d{1,3}\s+anni\b", re.I)),
    ("lavoro", re.compile(r"\b(?:lavoro come|faccio il|faccio la|sono un|sono una|di mestiere|la mia professione)\b.{2,120}", re.I)),
    ("luogo", re.compile(r"\b(?:abito|vivo|risiedo)\s+(?:a|ad|in|nella|nel)\s+(.{2,80})", re.I)),
    ("relazione", re.compile(r"\b(?:mia moglie|mio marito|mio figlio|mia figlia|mio padre|mia madre|mio fratello|"
                            r"mia sorella|il mio cane|il mio gatto|la mia compagna|il mio compagno|la mia fidanzata|"
                            r"il mio fidanzato)\b.{2,120}", re.I)),
    ("abitudine", re.compile(r"\b(?:di solito|tutte le (?:mattine|sere)|ogni giorno|ogni (?:lunedì|martedì|mercoledì|"
                            r"giovedì|venerdì|sabato|domenica))\b.{3,140}", re.I)),
    ("obiettivo", re.compile(r"\b(?:voglio imparare|sto imparando|il mio obiettivo|vorrei diventare|sto studiando)\b.{3,140}", re.I)),
]
SKIP = re.compile(r"\b(?:meteo|che ore|che giorno|accendi|spegni|alza|abbassa|apri|chiudi|calcola|quanto fa)\b", re.I)


def facts(text: str) -> list:
    text = " ".join(text.split())
    if len(text) < 6 or SKIP.search(text):
        return []
    out, seen = [], set()
    for kind, pattern in DURABLE:
        m = pattern.search(text)
        if not m:
            continue
        phrase = (m.group(1) if m.groups() else m.group(0)).strip(" .,;:!?«»\"'")
        phrase = phrase[:160]
        key = phrase.lower()[:40]
        if len(phrase) >= 3 and key not in seen:
            seen.add(key)
            out.append({"kind": kind, "text": phrase})
    return out[:3]
