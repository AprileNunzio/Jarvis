import re

from features.home_assistant.nlu.calls import build_call, is_sensitive
from features.home_assistant.nlu.matching import (Catalog, detect_action, detect_params, match_areas, match_domains,
                                                  resolve_targets)
from features.home_assistant.nlu.text import find_phrase, norm, stem
from features.home_assistant.nlu.vocabulary import PROTOCOLS, QUERY_RE, DOMAIN_TOKEN_STEMS


def _names_hit(t: str, cat: Catalog) -> bool:
    tokens = [stem(w) for w in t.split()]
    return any(find_phrase(tokens, ph) >= 0 for e in cat.controllable() for ph in e["names"]
               if not (len(ph) == 1 and ph[0] in DOMAIN_TOKEN_STEMS))


def parse_command(text: str, cat: Catalog) -> dict | None:
    t = norm(text)
    action = detect_action(t)
    params = detect_params(t)
    tokens = [stem(w) for w in t.split()]
    domains = match_domains(tokens)
    if params.get("scene_words") and "scene" in domains:
        domains = ["scene"]
    if action is None and not (params.get("rgb") or params.get("kelvin") or params.get("percent")
                               or params.get("temperature")):
        return None
    if action in ("up", "down") and re.search(r"\b(volume|audio)\b", t):
        domains = ["media_player"]
    if action in ("up", "down") and re.search(r"\b(temperatura|riscaldamento|gradi)\b", t):
        domains = ["climate"]
    if action is None:
        action = "set"
    if not domains and action == "clean":
        domains = ["vacuum"]
    if not domains and action in ("on", "off") and re.search(r"\btutt[oaie]\b", t) and not _names_hit(t, cat):
        domains = ["light", "media_player", "fan"] if action == "off" else ["light"]
    if not domains and params.get("temperature") is not None:
        domains = ["climate", "water_heater"]

    res = resolve_targets(t, cat, action, domains, params)
    if res["how"] == "ambiguo":
        rooms = res.get("rooms", [])
        return {"kind": "ask", "speech": "In quale stanza?" + (f" Per esempio {', '.join(rooms[:4])}." if rooms else "")}
    if not res["entities"]:
        return None

    calls: dict = {}
    targets, sensitive = [], False
    for e in res["entities"]:
        call = build_call(action, e, params)
        if call is None:
            continue
        service, data = call
        sensitive = sensitive or is_sensitive(e["domain"], service, e)
        key = (e["domain"], service, tuple(sorted((k, str(v)) for k, v in data.items())))
        calls.setdefault(key, {"domain": e["domain"], "service": service, "entity_ids": [], "data": data})
        calls[key]["entity_ids"].append(e["entity_id"])
        targets.append(e["entity_id"])
    if not calls:
        return {"kind": "unsupported", "action": action, "entities": [e["entity_id"] for e in res["entities"]]}
    return {"kind": "command", "action": action, "calls": list(calls.values()), "entities": targets,
            "area_ids": res["area_ids"], "how": res["how"], "params": {k: v for k, v in params.items() if k != "rgb"},
            "sensitive": sensitive}


def parse_query(text: str, cat: Catalog) -> dict | None:
    t = norm(text)
    tokens = [stem(w) for w in t.split()]
    area_ids, whole = match_areas(tokens, cat)
    protocol = next((p for rx, p in PROTOCOLS if re.search(rx, t)), None)
    q = {"kind": "query", "area_ids": area_ids, "whole": whole, "protocol": protocol}
    if re.search(r"\b(chi (e|c e|ce) (in|a) casa|chi (e|c e) a casa|ce qualcuno (in|a) casa|c e qualcuno (in|a) casa|"
                 r"chi e rientrato|chi e uscito|siamo soli)\b", t):
        return q | {"topic": "who_home"}
    if re.search(r"\b(quando|ultima volta|ultimo movimento)\b", t) and re.search(r"\b(moviment|passat|qualcuno|presenz)", t):
        return q | {"topic": "last_motion"}
    if re.search(r"\b(moviment\w*|presenz\w*|occupat\w*|liber[ae]|c e qualcuno|ce qualcuno|chi c e|chi ce|"
                 r"dove (sono|e|si trova|ci sono)|in quale stanza|in che stanza)\b", t) and \
            (area_ids or whole or re.search(r"\b(stanz\w*|dove|casa|moviment\w*|presenz\w*)\b", t)):
        return q | {"topic": "presence"}
    if re.search(r"\b(temperatura|quanti gradi|che gradi|umidita|quanto fa (caldo|freddo)|fa caldo|fa freddo)\b", t) \
            and not detect_action(t):
        return q | {"topic": "climate_read"}
    if re.search(r"\b(porte|finestre|finestra|porta|cosa e aperto|aperture|chi ha lasciato)\b", t) and \
            re.search(r"\b(apert\w*|chius\w*)\b", t) and not detect_action(t):
        return q | {"topic": "open"}
    if protocol or re.search(r"\b(quanti|quante|quali|che|elenca|mostrami)\b.*\b(dispositiv\w*|apparecch\w*|sensor\w*|"
                             r"entita|device)\b", t) or re.search(r"\b(dispositivi|sensori) (in|della|del|nel|nella)\b", t):
        return q | {"topic": "inventory", "domains": match_domains(tokens)}
    if re.search(r"\b(stato della casa|situazione (in|della|a) casa|com e la casa|riepilogo (della )?casa|"
                 r"come sta la casa|hai studiato la casa|conosci la casa|com e casa)\b", t):
        return q | {"topic": "home_summary"}
    if QUERY_RE.search(t) and not detect_action(t):
        domains = match_domains(tokens)
        if domains or area_ids:
            res = resolve_targets(t, cat, None, domains, {})
            named = [e["entity_id"] for e in res["entities"]] if res["how"] == "nome" else []
            if named or domains:
                return q | {"topic": "state", "domains": domains, "entities": named}
    return None


def parse(text: str, cat: Catalog) -> dict | None:
    t = norm(text)
    if QUERY_RE.search(t) and not re.search(r"\b(puoi|potresti|riesci a)\b", t):
        q = parse_query(text, cat)
        if q:
            return q
    return parse_command(text, cat) or parse_query(text, cat)


def looks_like_home(text: str) -> bool:
    t = norm(text)
    return bool(detect_action(t)) and bool(match_domains([stem(w) for w in t.split()]))
