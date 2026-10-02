import re
from datetime import date, datetime, timedelta

from state import store

from features.google import panels
from features.google.commands import Ctx
from features.google.constants import DAYS_IT
from features.google.timeparse import (
    parse_day,
    parse_duration,
    parse_time,
    say_day,
    strip_phrase,
)

_ADD_TRIGGER = re.compile(r"^.*?\b(?:aggiungi|segna|metti|inserisci|crea|fissa|programma|annota)(?:mi)?\b\s*"
                          r"(?:(?:un|l')\s*(?:appuntamento|evento|impegno)\s*)?"
                          r"(?:(?:in|nel(?:l[ao'])?|sul(?:l[ao'])?|al(?:l[ao'])?)\s*(?:mia\s+|mio\s+)?"
                          r"(?:agenda|calendario|appuntament[oi])\s*)?", re.I)
_DEL_TRIGGER = re.compile(r"^.*?\b(?:cancella|elimina|annulla|togli|rimuovi)(?:mi)?\b\s*(?:l'|il |lo |la )?"
                          r"(?:appuntamento|evento|impegno|riunione)?\s*(?:di |del |della |con |per )?", re.I)


def day_range(text: str) -> tuple[datetime, datetime, str]:
    now = datetime.now().astimezone()
    t = text.lower()
    if re.search(r"\b(?:settimana|prossimi giorni|prossimi impegni|prossimi appuntamenti)\b", t):
        return now, now + timedelta(days=7), "nei prossimi sette giorni"
    if re.search(r"\b(?:mese|prossime settimane)\b", t):
        return now, now + timedelta(days=30), "nei prossimi trenta giorni"
    d, _ = parse_day(t)
    if d:
        start = datetime.combine(d, datetime.min.time()).astimezone()
        if d == now.date():
            start = now if "stasera" not in t else max(now, start.replace(hour=17))
        return start, datetime.combine(d, datetime.max.time()).astimezone(), say_day(d)
    if re.search(r"\b(?:prossim[oi]|dopo|next)\b", t):
        return now, now + timedelta(days=30), "prossimo"
    return now, datetime.combine(now.date(), datetime.max.time()).astimezone(), "oggi"


def _when(e: dict, multi: bool) -> str:
    time_txt = "tutto il giorno" if e["all_day"] else f"alle {e['start']:%H:%M}"
    return f"{say_day(e['start'].date())} {time_txt}" if multi else time_txt


async def agenda(text: str, ctx: Ctx) -> tuple[str, dict]:
    start, end, label = day_range(text)
    events = await ctx.session.events(start, end, 1 if label == "prossimo" else 25)
    if label == "prossimo":
        if not events:
            return f"{ctx.name}, non ha appuntamenti nei prossimi trenta giorni.", {"mode": "face"}
        e = events[0]
        return (f"{ctx.name}, il prossimo appuntamento è {_when(e, True)}: {e['title']}"
                + (f", a {e['where']}." if e["where"] else "."), {"mode": "face"})
    if not events:
        free = "è libero" if label in ("oggi", "domani") or label in DAYS_IT else "non ha appuntamenti"
        return f"{ctx.name}, {label} {free}: nessun impegno in agenda.", {"mode": "face"}
    multi = (end - start).days >= 1
    parts = [f"{_when(e, multi)} {e['title']}" for e in events[:6]]
    speech = (f"{ctx.name}, {label} ha {len(events)} impegn{'o' if len(events) == 1 else 'i'}: "
              + "; ".join(parts) + ("; e altri." if len(events) > 6 else "."))
    return speech, {"mode": "focus", "title": f"Agenda di {ctx.name} — {label}", "subtitle": ctx.email,
                    "panels": [panels.calendar(events, label, ctx.name)]}


async def add(text: str, ctx: Ctx) -> tuple[str, dict]:
    body = _ADD_TRIGGER.sub("", text, count=1)
    body = re.sub(r"\b(?:in|nel(?:l[ao'])?|sul(?:l[ao'])?)\s*(?:mia\s+|mio\s+)?(?:agenda|calendario)\b", " ", body, flags=re.I)
    d, dm = parse_day(body)
    hm, tm = parse_time(body)
    minutes, durm = parse_duration(body)
    title = strip_phrase(body, dm, tm, durm)
    title = re.sub(r"^(?:che|di|per|un|una|l'|il|lo|la|appuntamento|evento)\s+", "", title, flags=re.I).strip()
    if not title:
        return "Cosa devo segnare in agenda? Per esempio «aggiungi in agenda dentista giovedì alle 17».", {"mode": "face"}
    title = title[0].upper() + title[1:]
    d = d or date.today()
    if hm:
        start = datetime.combine(d, datetime.min.time()).replace(hour=hm[0], minute=hm[1]).astimezone()
        if start < datetime.now().astimezone() and not dm:
            start += timedelta(days=1)
        clash = [e for e in await ctx.session.events(start, start + timedelta(minutes=minutes or 60), 5) if not e["all_day"]]
        await ctx.session.add_event(title, start, False, minutes or 60)
        speech = f"Fatto, {ctx.name}: {title}, {say_day(start.date())} alle {start:%H:%M}, è nella sua agenda."
        if clash:
            speech += f" Attenzione: si sovrappone a {clash[0]['title']}."
    else:
        await ctx.session.add_event(title, datetime.combine(d, datetime.min.time()).astimezone(), True)
        speech = f"Fatto, {ctx.name}: {title} è in agenda per {say_day(d)}, tutto il giorno."
    store.event("INFO", f"Agenda di {ctx.name}: aggiunto «{title}»", "google")
    return speech, {"mode": "face"}


async def delete(text: str, ctx: Ctx) -> tuple[str, dict]:
    body = _DEL_TRIGGER.sub("", text, count=1)
    d, dm = parse_day(body)
    hint = strip_phrase(body, dm).lower().strip(" ?!.")
    now = datetime.now().astimezone()
    start = datetime.combine(d, datetime.min.time()).astimezone() if d else now
    events = await ctx.session.events(start, start + timedelta(days=1 if d else 30), 50)
    words = [w for w in re.findall(r"[\wÀ-ÿ]{3,}", hint)]
    found = [e for e in events if words and all(w in e["title"].lower() for w in words)] or \
            [e for e in events if words and any(w in e["title"].lower() for w in words)]
    if not found:
        return f"{ctx.name}, non trovo un appuntamento «{hint}» da cancellare.", {"mode": "face"}
    if len(found) > 1 and not d:
        options = "; ".join(f"{e['title']} {_when(e, True)}" for e in found[:3])
        return f"Ne ho trovati {len(found)}: {options}. Dimmi anche il giorno.", {"mode": "face"}
    e = found[0]
    await ctx.session.delete_event(e["cal_id"], e["id"])
    store.event("INFO", f"Agenda di {ctx.name}: cancellato «{e['title']}»", "google")
    return f"Ho cancellato {e['title']} di {_when(e, True)}.", {"mode": "face"}


async def free(text: str, ctx: Ctx) -> tuple[str, dict]:
    d, _ = parse_day(text.lower())
    d = d or date.today()
    slots = await ctx.session.free_slots(d)
    day_start = datetime.combine(d, datetime.min.time()).astimezone()
    busy = await ctx.session.events(day_start, day_start + timedelta(days=1), 25)
    if not slots:
        return f"{ctx.name}, {say_day(d)} sei impegnato tutto il giorno tra le 8 e le 20.", {"mode": "face"}
    parts = [f"dalle {a:%H:%M} alle {b:%H:%M}" for a, b in slots]
    speech = f"{ctx.name}, {say_day(d)} sei libero " + ", ".join(parts[:-1]) + (" e " if len(parts) > 1 else "") + parts[-1] + "."
    return speech, {"mode": "focus", "title": f"Tempo libero — {say_day(d)}", "subtitle": ctx.email,
                    "panels": [panels.free(d, slots, busy)]}
