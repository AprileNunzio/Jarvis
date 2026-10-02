import hashlib
import statistics
from collections import defaultdict
from datetime import date, datetime

from features.automations import sun

WINDOW_DAYS = 21
TIME_SPAN = 30
SUN_SPAN = 20
FOLLOW_UP = 300
GROUPS = {"all": (range(7), "ogni giorno", 5), "weekdays": (range(5), "nei giorni feriali", 5),
          "weekend": ((5, 6), "nel fine settimana", 4)}
STATES = {"on": "accende", "off": "spegne", "open": "apre", "closed": "chiude", "locked": "chiude a chiave",
          "unlocked": "apre la serratura", "heat": "accende il riscaldamento di", "cool": "accende il raffrescamento di",
          "playing": "fa partire", "paused": "mette in pausa", "idle": "ferma"}


def service_for(entity: str, state: str) -> tuple[str, dict] | None:
    domain = entity.split(".")[0]
    if domain in ("light", "switch", "fan", "input_boolean", "media_player") and state in ("on", "off"):
        return f"{domain}.turn_{state}", {}
    if domain == "media_player" and state in ("playing", "paused", "idle"):
        return f"media_player.{'media_play' if state == 'playing' else 'media_pause' if state == 'paused' else 'media_stop'}", {}
    if domain == "cover" and state in ("open", "closed"):
        return f"cover.{'open' if state == 'open' else 'close'}_cover", {}
    if domain == "lock" and state in ("locked", "unlocked"):
        return f"lock.{'lock' if state == 'locked' else 'unlock'}", {}
    if domain == "climate" and state in ("heat", "cool", "off", "auto", "heat_cool"):
        return "climate.set_hvac_mode", {"hvac_mode": state}
    return None


def _hm(minutes: float) -> str:
    m = int(round(minutes / 5) * 5) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def _cluster(values: list[float], span: float) -> list[float]:
    values = sorted(values)
    best: list[float] = []
    j = 0
    for i in range(len(values)):
        while values[i] - values[j] > span * 2:
            j += 1
        if i - j + 1 > len(best):
            best = values[j:i + 1]
    return best


def _pid(*parts) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:10]


def _sunset_minutes(day: date) -> float | None:
    t = sun.times(day).get("sunset")
    return t.hour * 60 + t.minute if t else None


def mine(rows: list[tuple], names: dict, threshold: float = 0.7, now: float | None = None) -> list[dict]:
    now = now or datetime.now().timestamp()
    since = now - WINDOW_DAYS * 86400
    rows = [r for r in rows if r[0] >= since]
    observed: dict[str, set] = defaultdict(set)
    firsts: dict[tuple, dict[date, float]] = defaultdict(dict)
    actions, arrivals = [], []
    for at, entity, state, wd, mins, people, sun_up, kind in rows:
        day = datetime.fromtimestamp(at).date()
        for g, (days, _, _) in GROUPS.items():
            if wd in days:
                observed[g].add(day)
        if kind == "action":
            actions.append((at, entity, state, sun_up))
            key = (entity, state)
            if day not in firsts[key] or mins < firsts[key][day]:
                firsts[key][day] = mins
        elif kind == "arrival":
            arrivals.append(at)
    out = []
    for (entity, state), per_day in firsts.items():
        if not service_for(entity, state):
            continue
        best = None
        for g, (days, label, min_days) in GROUPS.items():
            values = [m for d, m in per_day.items() if d.weekday() in days]
            cluster = _cluster(values, TIME_SPAN)
            seen = len(observed[g]) or 1
            conf = len(cluster) / seen
            if len(cluster) >= min_days and conf >= threshold:
                cand = {"kind": "time", "group": g, "group_label": label, "minutes": statistics.median(cluster),
                        "support": len(cluster), "observed": seen, "confidence": round(conf, 2),
                        "spread": statistics.pstdev(cluster) if len(cluster) > 1 else 0}
                if not best or conf > best["confidence"] + 0.15 or (g == "all" and conf >= best["confidence"] - 0.05):
                    best = cand
        deltas = []
        for d, m in per_day.items():
            s = _sunset_minutes(d)
            if s is not None and abs(m - s) <= 120:
                deltas.append(m - s)
        sun_cluster = _cluster(deltas, SUN_SPAN)
        seen = len(observed["all"]) or 1
        if len(sun_cluster) >= 5 and len(sun_cluster) / seen >= threshold:
            spread = statistics.pstdev(sun_cluster)
            if not best or (len(sun_cluster) >= best["support"] - 1 and spread < best["spread"] * 0.7):
                best = {"kind": "sun", "group": "all", "group_label": "ogni giorno", "offset": statistics.median(sun_cluster),
                        "support": len(sun_cluster), "observed": seen, "confidence": round(len(sun_cluster) / seen, 2),
                        "spread": spread}
        if best:
            out.append(_suggestion(entity, state, best, names))
    if len(arrivals) >= 4:
        follow: dict[tuple, list] = defaultdict(list)
        for a in arrivals:
            done = set()
            for at, entity, state, sun_up in actions:
                if 0 <= at - a <= FOLLOW_UP and (entity, state) not in done and service_for(entity, state):
                    done.add((entity, state))
                    follow[(entity, state)].append(sun_up)
        for (entity, state), suns in follow.items():
            conf = len(suns) / len(arrivals)
            if len(suns) >= 4 and conf >= threshold:
                night = sum(1 for s in suns if not s) / len(suns) >= 0.8
                out.append(_suggestion(entity, state, {"kind": "arrival", "night": night, "support": len(suns),
                                                       "observed": len(arrivals), "confidence": round(conf, 2)}, names))
    return sorted(out, key=lambda s: -s["confidence"])


def _suggestion(entity: str, state: str, p: dict, names: dict) -> dict:
    name = names.get(entity) or entity
    verb = STATES.get(state, f"porta a «{state}»")
    service, data = service_for(entity, state)
    action = {"type": "ha", "service": service, "entity": entity}
    if data:
        action["data"] = data
    conditions = [{"type": "presence", "present": True}] if entity.split(".")[0] in ("light", "media_player") and state != "off" else []
    if p["kind"] == "time":
        at = _hm(p["minutes"])
        days = list(GROUPS[p["group"]][0])
        trigger = {"type": "time", "at": at, **({"days": days} if p["group"] != "all" else {})}
        text = f"{p['group_label']} verso le {at} {verb} {name}"
        title = f"{name}: {verb} alle {at}"
    elif p["kind"] == "sun":
        off = int(round(p["offset"] / 5) * 5)
        trigger = {"type": "sun", "event": "sunset", "offset": off}
        when = "al tramonto" if off == 0 else f"{abs(off)} minuti {'dopo il' if off > 0 else 'prima del'} tramonto"
        text = f"{when} {verb} {name}"
        title = f"{name}: {verb} {when}"
    else:
        trigger = {"type": "presence", "event": "person_arrived"}
        if p.get("night"):
            conditions = conditions + [{"type": "sun", "when": "night"}]
        text = f"quando arriva qualcuno{' e fa buio' if p.get('night') else ''} {verb} {name}"
        title = f"{name}: {verb} all'arrivo"
    spec = {"name": title[0].upper() + title[1:], "description": f"Proposta da Jarvis osservando le abitudini: {text} "
            f"({p['support']} volte su {p['observed']}).", "tags": ["abitudini"], "mode": "single", "cooldown": 600,
            "triggers": [trigger], "conditions": conditions, "actions": [action]}
    return {"id": _pid(p["kind"], entity, state, p.get("group", "")), "kind": p["kind"], "entity": entity, "state": state,
            "text": text, "confidence": p["confidence"], "support": p["support"], "observed": p["observed"], "automation": spec}
