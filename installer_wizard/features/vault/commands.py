import re
from datetime import date, timedelta

from features.vault import diary
from features.vault.service import enabled, vault

ASK = re.compile(r"\b(cosa|che cosa) (è|e') successo\b|\b(leggimi|leggi|apri) il diario\b|\bdiario di (oggi|ieri)\b|\bcom'è andata (oggi|ieri)\b", re.I)


async def answer(text: str) -> tuple[str, dict]:
    if not enabled() or not ASK.search(text):
        raise LookupError
    day = date.today() - timedelta(days=1) if re.search(r"\bieri\b", text, re.I) else date.today()
    data = diary.gather(day, vault.meta["requests"])
    label = "Ieri" if day != date.today() else "Oggi"
    saved = vault.read_diary(day)
    recap = ""
    if "## Riassunto" in saved:
        recap = saved.split("## Riassunto", 1)[1].strip().split("\n\n", 1)[0].strip()
    speech = f"{label}: {diary.facts_line(data)}." + (f" {recap}" if recap else "")
    if data["odd"]:
        speech += " Da notare: " + data["odd"][0]["text"].replace("Signore, ", "")
    return speech, {"mode": "face"}
