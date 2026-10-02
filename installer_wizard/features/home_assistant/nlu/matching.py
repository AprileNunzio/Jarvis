import re
from dataclasses import dataclass, field

from features.home_assistant.nlu.text import find_phrase, norm, phrase_stems, stem
from features.home_assistant.nlu.vocabulary import (ACTION_RES, AREA_SYNONYMS, COLOR_STEMS, DOMAIN_PHRASES,
                                                    FLOOR_WORDS, HVAC, KELVIN, PLURAL_WORDS, WHOLE_HOME,
                                                    DOMAIN_TOKEN_STEMS)


@dataclass
class Catalog:
    areas: dict = field(default_factory=dict)
    floors: dict = field(default_factory=dict)
    entities: dict = field(default_factory=dict)
    default_area: str | None = None
    occupied: list = field(default_factory=list)

    def controllable(self):
        return (e for e in self.entities.values() if e.get("controllable"))


def area_names(name: str, aliases: list, all_area_names: list[str]) -> list[tuple]:
    names = {phrase_stems(name)} | {phrase_stems(a) for a in aliases if a}
    n = norm(name)
    for group in AREA_SYNONYMS:
        if any(n == norm(g) or re.search(rf"\b{re.escape(norm(g))}\b", n) for g in group):
            for g in group:
                gs = phrase_stems(g)
                clash = any(o != name and find_phrase(list(phrase_stems(o)), gs) >= 0 for o in all_area_names)
                if not clash:
                    names.add(gs)
    return [x for x in names if x]


def detect_action(t: str) -> str | None:
    best = None
    for action, rx in ACTION_RES:
        m = rx.search(t)
        if m and (best is None or m.start() < best[1]):
            best = (action, m.start())
    return best[0] if best else None


def detect_params(t: str) -> dict:
    p: dict = {}
    toks = [stem(w) for w in t.split()]
    if m := re.search(r"(\d{1,3}(?:\.\d+)?)\s*(%|per ?cento)", t):
        p["percent"] = min(100.0, float(m.group(1)))
    elif re.search(r"\b(a meta|al 50)\b", t):
        p["percent"] = 50.0
    elif re.search(r"\b(al massimo|massim[ao]|al top|piena potenza)\b", t):
        p["percent"] = 100.0
    elif re.search(r"\b(al minimo|minim[ao])\b", t):
        p["percent"] = 1.0
    if m := re.search(r"(\d{1,2}(?:\.\d)?)\s*(gradi|°|c\b)", t):
        p["temperature"] = float(m.group(1))
    elif "percent" not in p and (m := re.search(r"\b(?:a|al|su|sui|ai)\s+(\d{1,3}(?:\.\d)?)\b(?!\s*(minut|secon|or[ae]))", t)):
        p["number"] = float(m.group(1))
    for phrase, kelvin in KELVIN:
        if find_phrase(toks, phrase_stems(phrase)) >= 0:
            p["kelvin"] = kelvin
            break
    for tok in toks:
        if tok in COLOR_STEMS:
            p["color_name"], p["rgb"] = COLOR_STEMS[tok]
            p.pop("kelvin", None)
            break
    for rx, mode in HVAC:
        if re.search(rx, t):
            p["hvac"] = mode
            break
    if m := re.search(r"\b(scena|scenario|modalita|atmosfera)\s+(.+)$", t):
        p["scene_words"] = m.group(2)
    return p


def match_areas(tokens: list[str], cat: Catalog) -> tuple[list[str], bool]:
    found = []
    for aid, a in cat.areas.items():
        best = max((len(ph) for ph in a["names"] if find_phrase(tokens, ph) >= 0), default=0)
        if best:
            found.append((best, aid))
    joined = " ".join(tokens)
    for fid, f in cat.floors.items():
        if any(find_phrase(tokens, ph) >= 0 for ph in f["names"]):
            found += [(len(f["names"][0]), aid) for aid, a in cat.areas.items() if a.get("floor_id") == fid]
    for words, level in FLOOR_WORDS.items():
        if find_phrase(tokens, phrase_stems(words)) >= 0:
            fl = [fid for fid, f in cat.floors.items() if f.get("level") == level]
            found += [(2, aid) for aid, a in cat.areas.items() if a.get("floor_id") in fl]
    found.sort(reverse=True)
    ids = list(dict.fromkeys(aid for _, aid in found))
    whole = bool(WHOLE_HOME.search(joined)) and not ids
    return ids, whole


def match_domains(tokens: list[str]) -> list[str]:
    hits = []
    for d, phrases in DOMAIN_PHRASES.items():
        pos = [find_phrase(tokens, ph) for ph in phrases]
        pos = [p for p in pos if p >= 0]
        if pos:
            hits.append((min(pos), d))
    return [d for _, d in sorted(hits)]


def _name_score(e: dict, tokens: list[str], token_set: set, area_stems: set) -> float:
    best = 0.0
    for ph in e["names"]:
        if len(ph) >= 1 and find_phrase(tokens, ph) >= 0 and not (len(ph) == 1 and ph[0] in DOMAIN_TOKEN_STEMS):
            best = max(best, 100 + len(ph))
            continue
        distinct = [s for s in ph if s not in area_stems and s not in DOMAIN_TOKEN_STEMS and len(s) >= 3
                    and not s.isdigit()]
        if distinct:
            hit = sum(1 for s in distinct if s in token_set)
            if hit:
                best = max(best, 10 * hit / len(distinct) + hit)
    return best


DOMAIN_PRIORITY = ["light", "cover", "climate", "fan", "media_player", "switch", "lock", "vacuum", "scene", "script",
                   "alarm_control_panel", "humidifier", "water_heater", "valve", "siren", "lawn_mower", "input_boolean",
                   "button", "input_button", "remote", "select", "input_select", "number", "input_number", "automation"]


def _prio(domain: str) -> int:
    return DOMAIN_PRIORITY.index(domain) if domain in DOMAIN_PRIORITY else 99


def resolve_targets(t: str, cat: Catalog, action: str | None, domains: list[str], params: dict) -> dict:
    tokens = [stem(w) for w in t.split()]
    token_set = set(tokens)
    area_ids, whole = match_areas(tokens, cat)
    area_stems = {s for aid in cat.areas for ph in cat.areas[aid]["names"] for s in ph}
    words = set(t.split())
    plural = bool(words & PLURAL_WORDS)
    whole = whole or (not area_ids and bool(words & {"tutte", "tutti", "tutto", "ovunque"}))

    pool = [e for e in cat.controllable() if (not domains or e["domain"] in domains
                                              or (action in ("on", "off") and e["domain"] in ("switch", "input_boolean")
                                                  and "light" in domains and e.get("as_light")))]
    scored = [(s, e) for e in pool if (s := _name_score(e, tokens, token_set, area_stems)) > 0]
    if plural and domains and area_ids:
        scored = []
    if area_ids:
        in_area = [(s, e) for s, e in scored if e.get("area_id") in area_ids]
        scored = in_area or ([] if domains else scored)
    if scored:
        top = max(s for s, _ in scored)
        chosen = [e for s, e in scored if s >= top - 0.01]
        return {"entities": _one_per_device(chosen), "area_ids": area_ids, "how": "nome"}

    if not domains:
        return {"entities": [], "area_ids": area_ids, "how": "nessuno"}
    if area_ids:
        chosen = [e for e in pool if e.get("area_id") in area_ids]
        how = "stanza"
    elif whole:
        chosen, how = pool, "casa"
    else:
        chosen, how = [], ""
        for aid in [cat.default_area] + list(cat.occupied):
            if aid and (c := [e for e in pool if e.get("area_id") == aid]):
                chosen, how, area_ids = c, "stanza di Jarvis" if aid == cat.default_area else "stanza occupata", [aid]
                break
        if not chosen and len(pool) == 1:
            chosen, how = pool, "unico"
        if not chosen and plural:
            chosen, how = pool, "casa"
        if not chosen and pool:
            rooms = sorted({cat.areas[e["area_id"]]["name"] for e in pool if e.get("area_id") in cat.areas})
            return {"entities": [], "area_ids": [], "how": "ambiguo", "rooms": rooms}
    if chosen and not plural and not whole and len(chosen) > 1:
        groups = [e for e in chosen if e.get("is_group")]
        if groups:
            chosen = groups[:1]
    return {"entities": _one_per_device(chosen), "area_ids": area_ids, "how": how}


def _one_per_device(entities: list[dict]) -> list[dict]:
    best: dict = {}
    for e in entities:
        key = e.get("device_id") or e["entity_id"]
        if key not in best or _prio(e["domain"]) < _prio(best[key]["domain"]):
            best[key] = e
    return list(best.values())
