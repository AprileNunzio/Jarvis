import logging

from config import env_get
from state import store

from features.people import people

log = logging.getLogger("jarvis.welcome")
TTL = 180
ICONS = {"compleanno": "🎂", "onomastico": "🎉"}


def enabled() -> bool:
    return env_get("JARVIS_WELCOME", "1") != "0"


def _when(days: int) -> str:
    return "oggi" if days == 0 else "domani" if days == 1 else f"tra {days} giorni"


async def _weather(desk) -> None:
    from features.chat.skills.weather import weather_skill
    _, ui = await weather_skill("")
    panel = next((p for p in ui.get("panels", []) if p.get("type") == "forecast"), None)
    if panel:
        desk.show("weather", panel["data"], key="welcome:weather", ttl=TTL, intent=True)


def _reminders(desk) -> None:
    items = people.reminders(days=3)[:4]
    if not items:
        return
    first = items[0]
    text = " · ".join(f"{r['title']} {_when(r['days'])}" for r in items)
    desk.show("notice", {"icon": ICONS.get(first["type"], "⏰"), "title": "Prossimi giorni", "text": text},
              key="welcome:reminders", ttl=TTL, intent=True)


async def _google(profile: dict) -> None:
    from features.google.gservices import google
    from features.google.notify import notifier
    session = google.for_profile(profile)
    if session:
        notifier.briefed.pop(profile["slug"], None)
        await notifier.brief(profile, session)


async def welcome(slugs: list[str]) -> None:
    if not enabled():
        return
    from features.desktop.desk import desk
    steps = [("meteo", _weather(desk))]
    for slug in slugs:
        profile = people.load(slug)
        if profile:
            steps.append(("Google", _google(profile)))
    for name, coro in steps:
        try:
            await coro
        except Exception as exc:
            log.warning("Benvenuto: %s non disponibile (%s)", name, exc)
    for name, fn in (("promemoria", _reminders),):
        try:
            fn(desk)
        except Exception as exc:
            log.warning("Benvenuto: %s non disponibile (%s)", name, exc)
    store.event("INFO", f"Benvenuto con i widget per {', '.join(slugs)}", "vision")
