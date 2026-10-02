import re

from config import write_env
from state import store

from features.sounds.library import AMBIENTS
from features.sounds.policy import policy

FACE = {"mode": "face"}
DND = re.compile(r"\b(non disturbare|modalit[àa] (notte|silenzio(sa)?|notturna)|fai silenzio|stai zitto|silenzio)\b", re.I)
OFF = re.compile(r"\b(disattiva|togli|esci da|basta)\b.*\b(non disturbare|modalit[àa] (notte|silenzio(sa)?|notturna)|silenzio)\b"
                 r"|\b(riattiva|riaccendi|rimetti)\b.*\bsuoni\b|\bpuoi (tornare a )?parlare\b", re.I)
FOR = re.compile(r"\bper\s+(un['a]?|\d+(?:[.,]\d+)?|mezz['a]?)\s*(or[ae]|minut[oi])\b", re.I)
UNTIL_MORNING = re.compile(r"\b(fino a domattina|fino a domani|stanotte|per la notte)\b", re.I)
AMBIENT = re.compile(r"\b(metti|attiva|avvia|accendi|fammi sentire)\b.*\b(sottofondo|ambiente sonoro|rumore di fondo)\b", re.I)
AMBIENT_OFF = re.compile(r"\b(togli|spegni|ferma|disattiva)\b.*\b(sottofondo|ambiente sonoro|rumore di fondo)\b", re.I)
VOLUME = re.compile(r"\b(alza|aumenta|abbassa|diminuisci|riduci)\b.*\b(suoni|effetti( sonori)?)\b", re.I)
WORDS = {"pioggia": "rain", "reattore": "reactor", "spazio": "space", "onde": "ocean", "mare": "ocean", "oceano": "ocean",
         "laboratorio": "lab", "officina": "lab"}


def _minutes(text: str) -> float | None:
    m = FOR.search(text)
    if m:
        n = m.group(1).lower()
        value = 1.0 if n.startswith("un") else 0.5 if n.startswith("mezz") else float(n.replace(",", "."))
        return value * (60 if m.group(2).lower().startswith("or") else 1)
    if UNTIL_MORNING.search(text):
        from datetime import datetime, timedelta
        now = datetime.now()
        end = policy.settings()["quiet_end"]
        h, mi = (int(x) for x in end.split(":"))
        target = now.replace(hour=h, minute=mi, second=0)
        if target <= now:
            target += timedelta(days=1)
        return (target - now).total_seconds() / 60
    return None


async def answer(text: str) -> tuple[str, dict]:
    if OFF.search(text):
        return policy.clear_dnd() + ", signore.", FACE
    if AMBIENT_OFF.search(text):
        write_env({"JARVIS_SOUNDS_AMBIENT": "none"})
        store.touch()
        return "Sottofondo spento, signore.", FACE
    if AMBIENT.search(text):
        low = text.lower()
        choice = next((v for k, v in WORDS.items() if k in low), "reactor")
        write_env({"JARVIS_SOUNDS_AMBIENT": choice})
        store.touch()
        return f"Sottofondo «{AMBIENTS[choice]}» attivo, signore.", FACE
    m = VOLUME.search(text)
    if m:
        up = m.group(1).lower() in ("alza", "aumenta")
        value = max(0, min(100, policy.settings()["volume"] + (15 if up else -15)))
        write_env({"JARVIS_SOUNDS_VOLUME": str(value)})
        store.touch()
        return f"Effetti sonori al {value} per cento, signore.", FACE
    if DND.search(text) and len(text.split()) <= 12:
        return policy.set_dnd(_minutes(text), "a voce") + ", signore.", FACE
    raise LookupError
