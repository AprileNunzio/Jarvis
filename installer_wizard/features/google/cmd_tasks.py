import re
from datetime import date

from state import store

from features.google import panels
from features.google.commands import Ctx
from features.google.timeparse import parse_day, say_day, strip_phrase

_ADD = re.compile(r"^.*?\b(?:ricordami di|devo ricordarmi di|aggiungi (?:alla|nella|in) (?:mia )?(?:lista|to ?do|cose da fare|"
                  r"attività)(?: delle cose da fare)?|(?:aggiungi|crea|metti) (?:un'?|una )?(?:attività|task|"
                  r"cosa da fare))\s*:?\s*", re.I)
_DONE = re.compile(r"^.*?\b(?:ho fatto|ho finito|fatto|completat[ao]|segna (?:come )?fatt[ao]|spunta|completa)\b\s*"
                   r"(?:l'attività|il task|la cosa|dalla lista)?\s*(?:di\s+)?", re.I)


async def listing(text: str, ctx: Ctx) -> tuple[str, dict]:
    items = await ctx.session.tasks(25)
    if not items:
        return f"{ctx.name}, la sua lista è vuota: nessuna attività da fare.", {"mode": "face"}
    late = [t for t in items if t["due"] and date.fromisoformat(t["due"]) < date.today()]
    speech = (f"{ctx.name}, ha {len(items)} attività da fare: " + ", ".join(t["title"] for t in items[:5])
              + (" e altre." if len(items) > 5 else ".") + (f" {len(late)} sono in ritardo." if late else ""))
    return speech, {"mode": "focus", "title": f"Cose da fare di {ctx.name}", "subtitle": ctx.email,
                    "panels": [panels.tasks(items)]}


async def add(text: str, ctx: Ctx) -> tuple[str, dict]:
    title = _ADD.sub("", text, count=1)
    d, dm = parse_day(title)
    title = strip_phrase(title, dm)
    if not title:
        return "Cosa devo aggiungere alla lista?", {"mode": "face"}
    title = title[0].upper() + title[1:]
    await ctx.session.add_task(title, d)
    store.event("INFO", f"Attività di {ctx.name}: aggiunta «{title}»", "google")
    return f"Aggiunto alla sua lista, {ctx.name}: {title}" + (f", per {say_day(d)}." if d else "."), {"mode": "face"}


async def done(text: str, ctx: Ctx) -> tuple[str, dict]:
    hint = _DONE.sub("", text, count=1).lower().strip(" ?!.")
    words = re.findall(r"[\wÀ-ÿ]{3,}", hint)
    items = await ctx.session.tasks(50)
    found = [t for t in items if words and all(w in t["title"].lower() for w in words)] or \
            [t for t in items if words and any(w in t["title"].lower() for w in words)]
    if not found:
        return f"Non trovo «{hint}» tra le sue attività.", {"mode": "face"}
    task = found[0]
    await ctx.session.complete_task(task["id"])
    rest = [t for t in items if t["id"] != task["id"]]
    left = len(rest)
    speech = (f"Ottimo lavoro, {ctx.name}: «{task['title']}» è completata."
              + (" Te ne resta una." if left == 1 else f" Te ne restano {left}." if left else " La lista è vuota!"))
    return speech, {"mode": "focus", "title": f"Cose da fare di {ctx.name}", "subtitle": ctx.email,
                    "panels": [panels.tasks(rest, task["title"])]}
