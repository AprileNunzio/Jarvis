import re

import httpx

from state import store


def vision_skill() -> tuple[str, dict]:
    from features.people.presence import describe
    pres = store.presence or {}
    if pres.get("status") not in ("ok",):
        return "La webcam non è disponibile in questo momento.", {"mode": "face"}
    people = pres.get("people", [])
    speech = describe(people)
    items = [{"label": p["name"], "value": ("vicino" if p["near"] else "lontano")
              + (f" · {p['confidence'] * 100:.0f}%" if p["known"] else ""),
              "status": "ok" if p["known"] else "warn"} for p in people]
    return speech, {"mode": "focus", "title": "Cosa vedo", "subtitle": "Riconoscimento facciale locale",
                    "panels": [{"type": "image", "title": "Webcam", "src": "/api/vision/snapshot.jpg"},
                               {"type": "list", "title": f"Persone ({len(people)})",
                                "items": items or [{"label": "Nessuno", "value": "", "status": ""}]}]}


_NAME_RE = re.compile(r"\b(?:mi chiamo|il mio nome [èe]|chiamami)\s+([A-Za-zÀ-ÿ'][A-Za-zÀ-ÿ' ]{1,38})", re.I)


async def introduce_skill(text: str) -> tuple[str, dict]:
    from features.people import people
    m = _NAME_RE.search(text)
    if not m:
        return "Non ho capito il nome, puoi ripeterlo?", {"mode": "face"}
    name = " ".join(w.capitalize() for w in m.group(1).split()[:3]).strip(" .,!?")
    visible = [p for p in store.presence.get("people", []) if p.get("known")]
    target = next((p for p in visible if p.get("auto")), None)
    if target is None:
        if visible:
            return (f"La riconosco già come {visible[0]['name']}. Se desidera cambiare nome, può farlo dal pannello "
                    "Persone.", {"mode": "face"})
        return ("Non vedo nessuno davanti alla webcam a cui associare il nome. "
                "Si metta di fronte a me per qualche secondo e riprovi.", {"mode": "face"})
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.patch(f"http://127.0.0.1:8091/people/{target['slug']}", json={"name": name})
        r.raise_for_status()
    people.ensure(target["slug"], name)
    people.update(target["slug"], {"name": name})
    store.event("INFO", f"{target['name']} si è presentato come {name}", "people")
    return (f"Piacere di conoscerla, {name}. Da ora la riconoscerò e imparerò le sue abitudini.",
            {"mode": "face"})
