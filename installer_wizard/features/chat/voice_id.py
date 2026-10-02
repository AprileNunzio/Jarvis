import json
import re
import time
from pathlib import Path

from config import STATE_DIR

from features.chat import context as request_context
from features.people import identity

PRINTS = Path("/var/lib/jarvis/voiceprints")
OFFERS = STATE_DIR / "voice_offers.json"
OFFER_EVERY = 3 * 86400
ENROLL = re.compile(r"\b(?:impara|registra|memorizza|riconosci)\b.{0,15}\b(?:la )?mia voce\b|\btest (?:di lettura|vocale)\b",
                    re.I)
FORGET = re.compile(r"\b(?:dimentica|cancella|elimina)\b.{0,15}\b(?:la )?mia voce\b", re.I)
SENTENCES = (
    "Buongiorno Jarvis, oggi è una splendida giornata per imparare qualcosa di nuovo.",
    "Il gatto dorme sul divano mentre fuori piove e il vento muove le foglie.",
    "Vorrei sapere che tempo farà domani pomeriggio e se devo portare l'ombrello.",
    "Ricordami di comprare il pane, il latte e tre mele verdi al mercato.",
    "Accendi la luce del soggiorno e abbassa un po' il volume della musica.",
    "Quanti chilometri ci sono tra Roma e Milano passando per Firenze?",
    "La mia voce è unica: da oggi mi riconoscerai anche senza guardarmi.",
)


def status(slug: str) -> dict:
    try:
        meta = json.loads((PRINTS / f"{slug}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"samples": 0, "enrolled": False}
    return {"samples": int(meta.get("samples", 0)), "enrolled": bool(meta.get("enrolled")), "updated": meta.get("updated")}


def forget(slug: str) -> None:
    for ext in ("npy", "json"):
        (PRINTS / f"{slug}.{ext}").unlink(missing_ok=True)


def _offers() -> dict:
    try:
        return json.loads(OFFERS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def offer(voice_known: bool | None) -> str:
    if voice_known is not False:
        return ""
    profile = identity.current()
    if not profile or not identity.alone(profile) or status(profile["slug"])["enrolled"]:
        return ""
    offers = _offers()
    if time.time() - offers.get(profile["slug"], 0) < OFFER_EVERY:
        return ""
    offers[profile["slug"]] = time.time()
    OFFERS.write_text(json.dumps(offers), encoding="utf-8")
    name = identity.first_name(profile)
    return (f" A proposito, {name}: la riconosco dal volto ma non ancora dalla voce. "
            "Se desidera, mi dica «impara la mia voce» e facciamo un test di lettura di un minuto. È facoltativo.")


def command(text: str) -> tuple[str, dict] | None:
    if not (ENROLL.search(text) or FORGET.search(text)):
        return None
    profile = identity.current(request_context.voice.get())
    if not profile or not identity.present():
        return "Si metta davanti alla webcam, signore: prima devo vederla, così so a chi appartiene la voce.", {"mode": "face"}
    name, slug = identity.first_name(profile), profile["slug"]
    if FORGET.search(text):
        forget(slug)
        return f"Fatto, {name}: ho cancellato la sua impronta vocale.", {"mode": "face"}
    return (f"Perfetto, {name}. Legga ad alta voce le frasi che compaiono sullo schermo, una alla volta, "
            "con il suo tono normale.", {"mode": "enroll", "slug": slug, "name": name, "sentences": list(SENTENCES)})
