import re

from features.google import panels
from features.google.commands import Ctx


async def contact(text: str, ctx: Ctx) -> tuple[str, dict]:
    m = re.search(r"\b(?:di|del|della|dello|contatto)\s+([A-Za-zÀ-ÿ'][A-Za-zÀ-ÿ' ]{1,40})", text, re.I)
    who = re.sub(r"^(?:telefono|cellulare)\s+(?:di\s+)?", "", (m.group(1) if m else "").strip(" ?!."), flags=re.I)
    if not who:
        return "Di chi le serve il contatto, signore?", {"mode": "face"}
    found = await ctx.session.contacts(who)
    if not found:
        if not re.search(r"\b(?:rubrica|contatt[oi])\b", text, re.I):
            raise LookupError
        return f"Non trovo {who} nella sua rubrica, {ctx.name}.", {"mode": "face"}
    p = found[0]
    if re.search(r"\be-?mail\b", text, re.I) and p["emails"]:
        speech = f"L'email di {p['name']} è {p['emails'][0]}."
    elif p["phones"]:
        speech = f"Il numero di {p['name']} è {p['phones'][0]}."
    elif p["emails"]:
        speech = f"Di {p['name']} ho solo l'email: {p['emails'][0]}."
    else:
        speech = f"{p['name']} è in rubrica ma senza numero né email."
    return speech, {"mode": "focus", "title": p["name"], "subtitle": f"Rubrica di {ctx.name}",
                    "panels": [panels.contact(p)]}


async def drive(text: str, ctx: Ctx) -> tuple[str, dict]:
    q = re.sub(r"^.*?\b(?:cerca|trova|apri)(?:mi)?\s+(?:(?:nel|sul|su|in)\s+(?:google\s+)?drive\s*)?"
               r"(?:il |un |i |la |le )?(?:file|document[oi])?\s*(?:di |del |della |su |sul |chiamat[oi] )?", "",
               text, count=1, flags=re.I).strip(" ?!.\"'«»")
    if len(q) < 2:
        return "Cosa devo cercare nel suo Drive?", {"mode": "face"}
    files = await ctx.session.files(q)
    if not files:
        if not re.search(r"\bdrive\b", text, re.I):
            raise LookupError
        return f"Nel suo Drive non trovo nulla su «{q}».", {"mode": "face"}
    speech = f"Ho trovato {len(files)} file per «{q}». Il più recente è {files[0]['name']}."
    return speech, {"mode": "focus", "title": f"Drive — {q}", "subtitle": ctx.email, "panels": [panels.drive(files, q)]}


async def notes(text: str, ctx: Ctx) -> tuple[str, dict]:
    found = await ctx.session.notes(10)
    if not found:
        return f"{ctx.name}, non ha note in Keep.", {"mode": "face"}
    if not ctx.private:
        return f"{ctx.name}, ha {len(found)} note: gliele leggo quando sarà da solo.", {"mode": "face"}
    speech = f"Ha {len(found)} note. " + " ".join(f"{n['title'] or n['text'][:60]}." for n in found[:3])
    return speech, {"mode": "focus", "title": f"Note di {ctx.name}", "subtitle": "Google Keep",
                    "panels": [panels.notes(found)]}


async def note_add(text: str, ctx: Ctx) -> tuple[str, dict]:
    body = re.sub(r"^.*?\b(?:(?:aggiungi|crea|scrivi|prendi) (?:una |la )?not[ae]|annota(?:ti)? che)\s*:?\s*", "",
                  text, count=1, flags=re.I).strip()
    if not body:
        return "Cosa devo scrivere nella nota?", {"mode": "face"}
    await ctx.session.add_note(body)
    return f"Nota salvata nel suo Keep, {ctx.name}.", {"mode": "face"}
