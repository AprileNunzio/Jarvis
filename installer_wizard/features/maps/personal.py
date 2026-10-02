import re

from config import read_env, write_env
from state import store

from features.people import identity, people

KINDS = {"lavoro": "Lavoro", "ufficio": "Lavoro", "scuola": "Scuola", "università": "Università",
         "palestra": "Palestra", "casa": "Casa"}


def kind_of(name: str) -> str | None:
    return KINDS.get(name.lower().strip())


owner = identity.owner
present = identity.present
current = identity.current


def address(profile: dict, label: str) -> str:
    for row in profile.get("addresses") or []:
        if row.get("label") == label:
            parts = [row.get("street"), " ".join(x for x in (row.get("zip"), row.get("city")) if x),
                     row.get("province"), row.get("country")]
            return ", ".join(p for p in parts if p)
    return ""


def save_address(profile: dict, label: str, text: str) -> dict:
    rows = [r for r in profile.get("addresses") or [] if r.get("label") != label]
    rows.append({"label": label, "street": text.strip()[:200]})
    return people.update(profile["slug"], {"addresses": rows})


def commute(profile: dict) -> dict | None:
    when = str(profile.get("commute_time") or "").strip()
    match = re.match(r"^(\d{1,2})[:.](\d{2})$", when)
    if not match:
        return None
    lo, _, hi = (profile.get("commute_days") or "1-5").partition("-")
    return {"hour": int(match.group(1)), "minute": int(match.group(2)), "days": (int(lo), int(hi or lo)),
            "mode": profile.get("travel_mode") or "", "before": int(profile.get("commute_before") or 45)}


def set_commute(profile: dict, hour: int, minute: int) -> dict:
    return people.update(profile["slug"], {"commute_time": f"{hour:02d}:{minute:02d}"})


def migrate(places: dict) -> bool:
    env = read_env()
    legacy_time = env.get("JARVIS_MAPS_COMMUTE", "").strip()
    work = places.get("lavoro")
    target = owner()
    if not target or not (legacy_time or work):
        return False
    changes = {}
    if legacy_time and not target.get("commute_time"):
        changes["commute_time"] = legacy_time
        days = env.get("JARVIS_MAPS_COMMUTE_DAYS", "")
        if days in ("1-5", "1-6", "1-7", "6-7"):
            changes["commute_days"] = days
    if work and not address(target, "Lavoro"):
        rows = list(target.get("addresses") or [])
        rows.append({"label": "Lavoro", "street": work["label"]})
        changes["addresses"] = rows
    if changes:
        people.update(target["slug"], changes)
        store.event("INFO", f"Maps: lavoro e tragitto spostati nella scheda di {target.get('name')}", "maps")
    if legacy_time:
        write_env({"JARVIS_MAPS_COMMUTE": "", "JARVIS_MAPS_COMMUTE_DAYS": ""})
    return True


def overview() -> list[dict]:
    rows = []
    for p in people.all_profiles(light=True):
        c = commute(p)
        places = {label: address(p, label) for label in ("Lavoro", "Scuola", "Università", "Palestra")}
        places = {k: v for k, v in places.items() if v}
        if c or places:
            rows.append({"slug": p["slug"], "name": p.get("name"), "places": places,
                         "commute": f"{c['hour']:02d}:{c['minute']:02d}" if c else "", "mode": (c or {}).get("mode", "")})
    return rows

