import re
from datetime import date

import httpx

WMO = {
    0: ("Sereno", "clear"), 1: ("Prevalentemente sereno", "clear"), 2: ("Parzialmente nuvoloso", "partly"),
    3: ("Coperto", "cloudy"), 45: ("Nebbia", "fog"), 48: ("Nebbia con brina", "fog"),
    51: ("Pioviggine leggera", "drizzle"), 53: ("Pioviggine", "drizzle"), 55: ("Pioviggine intensa", "drizzle"),
    56: ("Pioviggine gelata", "drizzle"), 57: ("Pioviggine gelata", "drizzle"),
    61: ("Pioggia debole", "rain"), 63: ("Pioggia", "rain"), 65: ("Pioggia forte", "rain"),
    66: ("Pioggia gelata", "rain"), 67: ("Pioggia gelata forte", "rain"),
    71: ("Neve debole", "snow"), 73: ("Neve", "snow"), 75: ("Neve forte", "snow"), 77: ("Granelli di neve", "snow"),
    80: ("Rovesci", "rain"), 81: ("Rovesci", "rain"), 82: ("Rovesci violenti", "storm"),
    85: ("Rovesci di neve", "snow"), 86: ("Rovesci di neve forti", "snow"),
    95: ("Temporale", "storm"), 96: ("Temporale con grandine", "storm"), 99: ("Temporale con grandine", "storm"),
}
DAYS_IT = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
MONTHS_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
             "ottobre", "novembre", "dicembre"]


async def _locate(client: httpx.AsyncClient) -> dict:
    from features.location.locator import locator
    loc = await locator.current()
    if loc.get("lat") is None:
        raise ValueError("posizione sconosciuta")
    return loc


_PREPS = {"a", "ad", "di", "del", "per", "su", "sul", "in", "da", "nel", "verso"}
_PLACE_END = {"oggi", "domani", "dopodomani", "stasera", "stanotte", "stamattina", "adesso", "ora", "questa", "questo",
              "nei", "nel", "nella", "per", "a", "ad", "in", "e", "ma", "che", "come", "com'è", "fine", "weekend",
              "settimana", "prossimi", "prossima", "prossimo", "giorni", "tempo", "meteo", "sarà", "farà", "fa",
              *(d.lower() for d in DAYS_IT)}
_NOT_PLACE = {"tempo", "meteo", "previsioni", "casa", "qui", "qua", "fuori", "noi", "me", "te", "solito", *_PLACE_END}


def _weather_place(text: str) -> str | None:
    words = re.findall(r"[A-Za-zÀ-ÿ']+|[?.!,;]", text)
    for i, w in enumerate(words):
        bare = w.lower() in ("meteo", "previsioni") and i + 1 < len(words) and words[i + 1][:1].isupper()
        if w.lower() not in _PREPS and not bare:
            continue
        name = []
        for x in words[i + 1:i + 5]:
            if not x[0].isalpha() or x.lower() in _PLACE_END:
                break
            name.append(x)
        while name and name[-1].lower() in ("di", "del", "la", "il"):
            name.pop()
        if name and name[0].lower() not in _NOT_PLACE:
            return " ".join(name)
    return None


def _day_index(text: str) -> int | None:
    t = text.lower()
    if "dopodomani" in t:
        return 2
    if "domani" in t:
        return 1
    for i, name in enumerate(DAYS_IT):
        if re.search(rf"\b{name.lower()}\b", t):
            return (i - date.today().weekday()) % 7
    return None


async def weather_skill(text: str = "") -> tuple[str, dict]:
    asked = _weather_place(text)
    async with httpx.AsyncClient(timeout=10) as client:
        if asked:
            from features.location.locator import search
            found = await search(asked, 1)
            if not found:
                return (f"Non ho trovato nessun luogo chiamato {asked}. Puoi ripetere il nome della città?",
                        {"mode": "face"})
            loc = {"name": found[0]["name"], "lat": found[0]["lat"], "lon": found[0]["lon"]}
        else:
            loc = await _locate(client)
        r = await client.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": loc["lat"], "longitude": loc["lon"], "timezone": "auto", "forecast_days": 7,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
                     "wind_speed_10m_max,sunrise,sunset",
        })
        data = r.json()

    cur, daily = data["current"], data["daily"]
    days = []
    for i, day in enumerate(daily["time"]):
        d = date.fromisoformat(day)
        desc, icon = WMO.get(daily["weather_code"][i], ("—", "cloudy"))
        days.append({
            "label": "Oggi" if i == 0 else ("Domani" if i == 1 else DAYS_IT[d.weekday()]),
            "date": f"{d.day} {MONTHS_IT[d.month - 1]}",
            "desc": desc, "icon": icon,
            "tmax": round(daily["temperature_2m_max"][i]), "tmin": round(daily["temperature_2m_min"][i]),
            "rain": daily["precipitation_probability_max"][i], "wind": round(daily["wind_speed_10m_max"][i]),
            "sunrise": daily["sunrise"][i][-5:], "sunset": daily["sunset"][i][-5:],
        })
    cur_desc, cur_icon = WMO.get(cur["weather_code"], ("—", "cloudy"))
    current = {"temp": round(cur["temperature_2m"]), "feels": round(cur["apparent_temperature"]),
               "humidity": cur["relative_humidity_2m"], "wind": round(cur["wind_speed_10m"]),
               "desc": cur_desc, "icon": cur_icon}

    rainy = [d["label"] for d in days[1:] if (d["rain"] or 0) >= 60]
    hottest = max(days, key=lambda d: d["tmax"])
    speech = (f"A {loc['name']} ora ci sono {current['temp']} gradi, {cur_desc.lower()}. "
              f"Nei prossimi sette giorni le massime vanno da {min(d['tmax'] for d in days)} a "
              f"{hottest['tmax']} gradi, con il picco {hottest['label'].lower()}. ")
    speech += (f"Pioggia probabile {', '.join(x.lower() for x in rainy[:3])}." if rainy
               else "Non sono previste piogge significative.")
    day = _day_index(text)
    if day:
        d = days[day]
        when = d["label"].lower() if day <= 1 else f"{d['label'].lower()} {d['date']}"
        speech = (f"{when.capitalize()} a {loc['name']}: {d['desc'].lower()}, massima {d['tmax']} e minima "
                  f"{d['tmin']} gradi" + (f", pioggia al {d['rain']} per cento." if (d["rain"] or 0) >= 30 else ".")
                  + f" Ora ci sono {current['temp']} gradi.")
    ui = {
        "mode": "focus",
        "title": f"Meteo — {loc['name']}",
        "subtitle": "Previsioni per i prossimi 7 giorni",
        "panels": [{"type": "forecast", "title": "Settimana", "data": {"current": current, "days": days,
                                                                        "location": loc["name"]}}],
    }
    return speech, ui
