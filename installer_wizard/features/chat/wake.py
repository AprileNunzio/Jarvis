import asyncio
import logging
import random
import time
from datetime import datetime, timedelta

import httpx
from state import store

from features.chat import speaker

log = logging.getLogger("jarvis.assistant")
OPENERS = (
    "Eccomi, {who}.", "Al suo servizio, {who}.", "Agli ordini, {who}.", "Sono qui, {who}.", "Presente, {who}.", "Dica pure, {who}.",
    "A sua disposizione, {who}.",
)
ALL_OK = (
    "Tutti i sistemi sono operativi.", "Sistemi nominali, nessuna anomalia.", "Tutto in ordine qui dentro.",
    "Reattore stabile e sistemi al cento per cento.", "Nessun allarme: possiamo procedere.",
)
LATE = ("Ore piccole anche stanotte, vedo.", "Il resto della casa dorme: parliamo sottovoce.")
_recent: list[str] = []


def _pick(options: tuple) -> str:
    fresh = [o for o in options if o not in _recent] or list(options)
    choice = random.choice(fresh)
    _recent.append(choice)
    del _recent[:-6]
    return choice


def _systems() -> tuple[str, list[str]]:
    broken = [c.get("label", "") for c in (store.components or {}).values() if c.get("status") not in ("ok", None)]
    if not broken:
        return _pick(ALL_OK), []
    names = ", ".join(broken[:2])
    return f"Quasi tutto operativo: tengo d'occhio {names}.", broken


async def _next_event() -> dict | None:
    from features.google.gservices import google
    from features.people import identity
    profile = identity.current()
    session = google.for_profile(profile) if profile else None
    if not session or not session.ready("calendar"):
        return None
    now = datetime.now().astimezone()
    events = [e for e in await session.events(now, now + timedelta(hours=12), 5) if not e["all_day"]]
    return events[0] if events else None


async def _weather() -> dict | None:
    from features.chat.skills.weather import weather_skill
    _, ui = await weather_skill("")
    panel = next((p for p in ui.get("panels", []) if p.get("type") == "forecast"), None)
    return (panel or {}).get("data", {}).get("current")


async def _safe(coro, timeout: float):
    try:
        return await asyncio.wait_for(coro, timeout)
    except (asyncio.TimeoutError, httpx.HTTPError, ValueError, KeyError, LookupError) as exc:
        log.debug("Informazione per il saluto non disponibile: %s", exc)
        return None


async def greeting() -> dict:
    who = speaker.name() or "signore"
    status, broken = _systems()
    event, weather = await asyncio.gather(_safe(_next_event(), 3.0), _safe(_weather(), 3.0))
    parts = [_pick(OPENERS).format(who=who), status]
    hour = time.localtime().tm_hour
    if hour < 5 or hour >= 23:
        parts.append(_pick(LATE))
    items = []
    if event:
        minutes = max(1, round((event["start"] - datetime.now().astimezone()).total_seconds() / 60))
        if minutes <= 90:
            parts.append(f"Tra {minutes} minuti ha {event['title']}.")
        items.append({"icon": "📅", "value": event["start"].strftime("%H:%M"), "label": event["title"][:24]})
    if weather:
        items.append({"icon": "🌡", "value": f"{weather.get('temp')}°", "label": str(weather.get("desc", ""))[:24]})
    items.append({"icon": "🛡" if not broken else "⚠️", "value": "OK" if not broken else str(len(broken)),
                  "label": "sistemi" if not broken else "da controllare"})
    return {"reply": " ".join(parts), "card": {"kind": "brief", "who": who, "items": items[:3],
                                               "text": "Come posso aiutarla?"}}
