import re

from features.actions.common import note_gap, sh
from features.actions.device_lookup import candidates

_DEVICE_NAMES = [
    re.compile(
        r"(?:chiamat[oa]|di nome|nominat[oa]|che si chiama|denominat[oa])\s+[«\"']?([\w\s\-.'’]{2,40}?)[»\"']?"
        r"(?:\s+e\s+(?:dimmi|mostrami|dammi)|\s+(?:in|nella|sulla)\s+rete|\s*[,.?!]|$)",
        re.I,
    ),
    re.compile(
        r"\b(?:ip|indirizzo)\s+(?:ip\s+)?(?:locale\s+)?(?:del|dello|della|di|dell'|di un|di una)\s*([\w\s\-.'’]{2,40}?)(?:\s*[,.?!]|$)",
        re.I,
    ),
    re.compile(
        r"\b(?:trova|cerca|trovami|dov'?[èe])\s+(?:il|lo|la|l'|mio|mia|un|una)?\s*([\w\s\-.'’]{2,40}?)\s+(?:in|nella|sulla)\s+rete",
        re.I,
    ),
]


def _device_wanted(text: str) -> str:
    for pattern in _DEVICE_NAMES:
        m = pattern.search(text)
        if m:
            name = re.sub(r"^(?:mio|mia|il|lo|la|l'|un|una)\s+", "", m.group(1).strip(" .'’"), flags=re.I)
            name = re.sub(r"^(?:dispositiv[oi]|apparecchi[oi]|device)\s*", "", name, flags=re.I).strip()
            if name:
                return name
    return ""


async def device_action(text: str) -> tuple[str, dict]:
    from features.network.explorer import explorer

    wanted = _device_wanted(text)
    if not wanted:
        raise LookupError("nome del dispositivo non trovato")
    if re.fullmatch(r"(router|gateway|modem|access point)(\s+di casa)?", wanted, re.I):
        _, out = await sh("ip", "route", "show", "default")
        gw = re.search(r"via (\S+)", out)
        if gw:
            return f"Il router è all'indirizzo {gw.group(1)}. Puoi aprirne il pannello da http://{gw.group(1)}", {
                "mode": "face"
            }
    if not explorer.subnet:
        await explorer.detect_subnet()
    found = await candidates(explorer, wanted)
    sure = [c for c in found if c["score"] >= 0.99]
    if not sure:
        note_gap(text, f"dispositivo «{wanted}» non trovato nella rete {explorer.subnet}")
        maybe = f" Forse intendi {found[0]['name']} ({found[0]['ip']})." if found else ""
        return (
            f"Ho cercato in tutta la rete {explorer.subnet}, per nome e tramite il router, ma nessun dispositivo "
            f"si chiama «{wanted}».{maybe} Se è acceso, assegnagli un nome dal pannello Rete e lo riconoscerò sempre.",
            {"mode": "face"},
        )
    best, others = sure[0], sure[1:3]
    state = "ed è connesso adesso" if best["online"] else "ma non risponde in questo momento, forse è in standby"
    speech = f"Ho trovato {best['name']}: il suo indirizzo IP locale è {best['ip']} {state}."
    if others:
        speech += " Nomi simili: " + ", ".join(f"{c['name']} ({c['ip']})" for c in others) + "."
    d = best["device"]
    kv = {
        "Nome": best["name"],
        "IP": best["ip"],
        "Stato": "online" if best["online"] else "non raggiungibile",
        "MAC": d.get("mac") or "—",
        "Produttore": d.get("vendor") or "—",
    }
    return speech, {
        "mode": "focus",
        "title": f"Trovato: {best['name']}",
        "subtitle": f"Rete {explorer.subnet}",
        "panels": [{"type": "kv", "title": "Dispositivo", "data": kv}],
    }
