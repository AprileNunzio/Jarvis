import logging
import time
from datetime import datetime

import httpx

from features.chat.skills.weather import weather_skill

log = logging.getLogger("jarvis.assistant")
TTL = 15 * 60
_cache: dict = {"at": 0.0, "data": None}


def _is_day(today: dict) -> bool:
    now = datetime.now().strftime("%H:%M")
    return today.get("sunrise", "06:30") <= now < today.get("sunset", "19:30")


async def current() -> dict:
    if _cache["data"] and time.time() - _cache["at"] < TTL:
        return _cache["data"]
    try:
        _, ui = await weather_skill("")
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        log.info("Meteo per lo sfondo non disponibile: %s", exc)
        return _cache["data"] or {"icon": "", "day": True}
    panel = next((p for p in ui.get("panels", []) if p.get("type") == "forecast"), {})
    data = panel.get("data") or {}
    cur, days = data.get("current") or {}, data.get("days") or [{}]
    result = {"icon": cur.get("icon", ""), "temp": cur.get("temp"), "wind": cur.get("wind", 0), "day": _is_day(days[0])}
    _cache.update(at=time.time(), data=result)
    return result
