import re

from state import store

_PLACE_RE = re.compile(r"\b(?:abito|vivo|mi trovo|ci troviamo|siamo|la casa [èe]|la mia casa [èe])\s+(?:a|ad|in)\s+"
                       r"([A-Za-zÀ-ÿ'][A-Za-zÀ-ÿ' ]{1,40})", re.I)
_SOURCE_IT = {"phone": "dalla posizione del tuo telefono", "browser": "dalla posizione del display",
              "wifi": "dalle reti Wi-Fi vicine", "lan": "dagli access point della rete di casa",
              "default": "dalla posizione che mi ha indicato", "ip": "dall'indirizzo Internet, quindi è approssimata"}


async def place_skill(text: str) -> tuple[str, dict]:
    from features.location.locator import locator, search
    m = _PLACE_RE.search(text)
    if m:
        name = re.split(r"\s+(?:e|ma|per|da|con|che)\s+|[,.!?]", m.group(1).strip())[0].strip()
        results = await search(name, 1)
        if not results:
            raise ValueError(f"luogo «{name}» non trovato")
        place = results[0]
        await locator.set_default(place["name"], place["lat"], place["lon"])
        store.event("INFO", f"Posizione di casa impostata a voce: {place['name']}", "location")
        return (f"Perfetto, ho memorizzato che siamo a {place['name']}"
                f"{', ' + place['detail'] if place.get('detail') else ''}. La userò per meteo e servizi locali.",
                {"mode": "face"})
    loc = await locator.current()
    if loc.get("lat") is None:
        return "Non so ancora dove ci troviamo: dimmi per esempio «abito a Napoli».", {"mode": "face"}
    return (f"Siamo a {loc['name']}: lo so {_SOURCE_IT.get(loc['source'], '')}."
            + (" Se è sbagliata dimmi «abito a» seguito dalla città." if loc["source"] == "ip" else ""), {"mode": "face"})
