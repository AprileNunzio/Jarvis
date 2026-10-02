import time
from datetime import datetime


def parse_ts(iso: str | None) -> float:
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return time.time()


def ago(ts: float) -> str:
    s = max(0, time.time() - ts)
    if s < 60:
        return "adesso"
    if s < 3600:
        m = int(s // 60)
        return f"{m} minut{'o' if m == 1 else 'i'} fa"
    if s < 86400:
        h = int(s // 3600)
        return f"{h} or{'a' if h == 1 else 'e'} fa"
    return time.strftime("il %d/%m alle %H:%M", time.localtime(ts))


def join_words(items: list[str]) -> str:
    items = [i for i in items if i]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " e " + items[-1] if items else ""


def capabilities(domain: str, attrs: dict) -> set[str]:
    sf = int(attrs.get("supported_features") or 0)
    c: set[str] = set()
    if domain == "light":
        modes = set(attrs.get("supported_color_modes") or [])
        if modes - {"onoff"} or "brightness" in attrs:
            c.add("brightness")
        if modes & {"hs", "xy", "rgb", "rgbw", "rgbww"}:
            c.add("color")
        if "color_temp" in modes or "rgbww" in modes:
            c.add("color_temp")
        if attrs.get("effect_list"):
            c.add("effect")
    elif domain == "cover":
        c |= {n for bit, n in ((1, "open"), (2, "close"), (4, "position"), (8, "stop"), (128, "tilt")) if sf & bit}
    elif domain == "climate":
        c |= {n for bit, n in ((1, "temperature"), (2, "range"), (8, "fan_mode"), (16, "preset"), (32, "swing")) if sf & bit}
        if attrs.get("hvac_modes"):
            c.add("hvac_mode")
    elif domain == "fan":
        c |= {n for bit, n in ((1, "speed"), (2, "oscillate"), (4, "direction"), (8, "preset")) if sf & bit}
    elif domain == "media_player":
        c |= {n for bit, n in ((1, "pause"), (4, "volume"), (8, "mute"), (16, "previous"), (32, "next"),
                               (128, "on"), (256, "off"), (2048, "source"), (4096, "stop"), (16384, "play")) if sf & bit}
    elif domain == "lock":
        if sf & 1:
            c.add("open")
    return c


CAP_IT = {"brightness": "luminosità", "color": "colore", "color_temp": "bianco caldo/freddo", "effect": "effetti",
          "open": "apri", "close": "chiudi", "position": "posizione", "stop": "stop", "tilt": "inclinazione",
          "temperature": "temperatura", "range": "intervallo", "fan_mode": "ventola", "preset": "preimpostazioni",
          "swing": "oscillazione", "hvac_mode": "modalità", "speed": "velocità", "oscillate": "oscillazione",
          "direction": "direzione", "pause": "pausa", "volume": "volume", "mute": "muto", "previous": "precedente",
          "next": "successivo", "on": "accendi", "off": "spegni", "source": "sorgente", "play": "play"}
