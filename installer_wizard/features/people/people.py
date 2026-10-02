import json
import re
import threading
import time
from collections import Counter
from datetime import date, timedelta

from config import STATE_DIR
from features.people.schema import FIELD_INDEX, RELATIONS, ROLES, SECTIONS

PEOPLE_DIR = STATE_DIR / "people"
SESSION_GAP = 5 * 60
MAX_SESSIONS = 500
DAYS_IT = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MONTHS_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
             "ottobre", "novembre", "dicembre"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
NAME_DAY_RE = re.compile(r"^(\d{1,2})[-/](\d{1,2})$")

NAME_DAYS = {
    "agata": "05-02", "agnese": "21-01", "alberto": "15-11", "alessio": "17-07", "alfonso": "01-08",
    "ambrogio": "07-12", "andrea": "30-11", "angela": "27-01", "anna": "26-07", "antonella": "13-06",
    "antonio": "13-06", "barbara": "04-12", "bartolomeo": "24-08", "benedetto": "11-07", "bernardo": "20-08",
    "biagio": "03-02", "bruno": "06-10", "camillo": "14-07", "carla": "04-11", "carlo": "04-11",
    "caterina": "29-04", "cecilia": "22-11", "chiara": "11-08", "cosimo": "26-09", "cristina": "24-07",
    "cristoforo": "25-07", "damiano": "26-09", "daniela": "21-07", "daniele": "21-07", "davide": "29-12",
    "domenico": "08-08", "elena": "18-08", "elisabetta": "17-11", "enrico": "13-07", "filippo": "26-05",
    "francesca": "09-03", "francesco": "04-10", "gabriele": "29-09", "gaetano": "07-08", "gennaro": "19-09",
    "giacomo": "25-07", "gianni": "24-06", "giorgia": "23-04", "giorgio": "23-04", "giovanni": "24-06",
    "giulia": "22-05", "giuseppe": "19-03", "giuseppina": "19-03", "gregorio": "03-09", "ignazio": "31-07",
    "leonardo": "06-11", "lorenza": "10-08", "lorenzo": "10-08", "luca": "18-10", "lucia": "13-12",
    "luciano": "07-01", "luigi": "21-06", "marcello": "16-01", "marco": "25-04", "maria": "12-09",
    "mario": "19-01", "marta": "29-07", "martina": "30-01", "martino": "11-11", "matteo": "21-09",
    "mattia": "14-05", "maurizio": "22-09", "michela": "29-09", "michele": "29-09", "monica": "27-08",
    "natale": "25-12", "nicola": "06-12", "nicoletta": "06-12", "nunzia": "25-03", "nunzio": "25-03",
    "paola": "26-01", "paolo": "29-06", "pasquale": "17-05", "patrizia": "25-08", "pietro": "29-06",
    "raffaele": "29-09", "raffaella": "29-09", "riccardo": "03-04", "rita": "22-05", "roberto": "17-09",
    "rocco": "16-08", "rosalia": "04-09", "samuele": "20-08", "santo": "01-11", "sebastiano": "20-01",
    "silvia": "03-11", "simona": "28-10", "simone": "28-10", "stefano": "26-12", "teresa": "15-10",
    "tommaso": "03-07", "valentino": "14-02", "vito": "15-06",
}

SYSTEM_KEYS = {"slug", "name", "created_at", "updated_at", "stats", "sessions", "voice", "has_face"}
_lock = threading.Lock()


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "persona"


def _path(slug: str):
    return PEOPLE_DIR / f"{slugify(slug)}.json"


def display_name(p: dict) -> str:
    full = " ".join(x for x in (p.get("first_name"), p.get("last_name")) if x).strip()
    return full or p.get("name") or p.get("slug", "")


def _blank(slug: str, name: str) -> dict:
    first, _, last = name.strip().partition(" ")
    return {
        "slug": slug, "name": name, "first_name": first, "last_name": last, "role": "guest",
        "consent": True, "share_health": False,
        "voice": {"tts_voice": "", "speed": 1.0, "voiceprint": None},
        "created_at": time.time(), "updated_at": time.time(),
        "stats": {"visits": 0, "total_seconds": 0, "first_seen": None, "last_seen": None},
        "sessions": [],
    }


def _migrate(p: dict) -> dict:
    if "first_name" not in p:
        first, _, last = (p.get("name") or "").partition(" ")
        p["first_name"], p["last_name"] = first, last
    prefs = p.pop("preferences", None)
    if isinstance(prefs, dict) and prefs:
        custom = p.setdefault("custom", [])
        custom.extend({"key": k, "value": str(v)} for k, v in prefs.items())
    p.setdefault("consent", True)
    return p


def load(slug: str) -> dict | None:
    try:
        return _migrate(json.loads(_path(slug).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


def save(profile: dict) -> None:
    PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
    profile["updated_at"] = time.time()
    profile["name"] = display_name(profile)
    path = _path(profile["slug"])
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(profile, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def ensure(slug: str, name: str) -> dict:
    with _lock:
        profile = load(slug)
        if profile is None:
            profile = _blank(slugify(slug), name)
            save(profile)
        return profile


def _clean(field: dict, value):
    t = field["type"]
    if value is None or value == "":
        return "" if t not in ("list", "tags", "bool") else ([] if t in ("list", "tags") else False)
    if t == "bool":
        return bool(value)
    if t == "number":
        try:
            return float(value) if "." in str(value) else int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field['label']}: numero non valido")
    if t == "date":
        if not DATE_RE.match(str(value)):
            raise ValueError(f"{field['label']}: data non valida")
        return str(value)
    if t == "select":
        if field.get("options") and str(value) not in field["options"]:
            raise ValueError(f"{field['label']}: valore non ammesso")
        return str(value)
    if t == "tags":
        items = value if isinstance(value, list) else str(value).split(",")
        return [str(x).strip()[:80] for x in items if str(x).strip()][:50]
    if t == "list":
        if not isinstance(value, list):
            raise ValueError(f"{field['label']}: elenco non valido")
        subfields = {f["key"]: f for f in field["fields"]}
        rows = []
        for row in value[:100]:
            if not isinstance(row, dict):
                continue
            clean = {k: _clean(subfields[k], v) for k, v in row.items() if k in subfields}
            if any(v not in ("", [], False, None) for v in clean.values()):
                rows.append(clean)
        return rows
    return str(value).strip()[:4000]


def update(slug: str, changes: dict) -> dict:
    with _lock:
        profile = load(slug)
        if profile is None:
            raise KeyError(slug)
        old_relations = list(profile.get("relations", []))
        for key, value in changes.items():
            if key == "voice":
                if not isinstance(value, dict):
                    raise ValueError("voce non valida")
                profile["voice"] = {**profile.get("voice", {}), **value}
            elif key in FIELD_INDEX:
                profile[key] = _clean(FIELD_INDEX[key][1], value)
            elif key == "name":
                first, _, last = str(value).strip().partition(" ")
                profile["first_name"], profile["last_name"] = first, last
        save(profile)
    if "relations" in changes:
        _sync_relations(profile, old_relations)
    return profile


def _sync_relations(profile: dict, old: list) -> None:
    me = profile["slug"]
    current = {(r.get("person"), r.get("type")) for r in profile.get("relations", []) if r.get("person")}
    previous = {(r.get("person"), r.get("type")) for r in old if r.get("person")}
    for other, rtype in current | previous:
        if other == me:
            continue
        inverse = RELATIONS.get(rtype, ("", "altro"))[1]
        with _lock:
            target = load(other)
            if target is None:
                continue
            rels = [r for r in target.get("relations", [])
                    if not (r.get("person") == me and r.get("auto_inverse"))]
            if (other, rtype) in current:
                rels.append({"type": inverse, "person": me, "auto_inverse": True})
            target["relations"] = rels
            save(target)


def delete(slug: str) -> bool:
    with _lock:
        path = _path(slug)
        if not path.exists():
            return False
        path.unlink()
    for p in all_profiles(light=True):
        rels = p.get("relations", [])
        kept = [r for r in rels if r.get("person") != slug]
        if len(kept) != len(rels):
            update(p["slug"], {"relations": kept})
    return True


def all_profiles(light: bool = False) -> list:
    PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for f in sorted(PEOPLE_DIR.glob("*.json")):
        p = load(f.stem)
        if not p:
            continue
        if not light:
            p["habits"] = habits(p)
            p["computed"] = computed(p)
            p.pop("sessions", None)
        out.append(p)
    return out


def get(slug: str) -> dict | None:
    p = load(slug)
    if p:
        p["habits"] = habits(p)
        p["computed"] = computed(p)
    return p


def name_day(p: dict) -> str:
    m = NAME_DAY_RE.match(str(p.get("name_day") or "").strip())
    if m:
        return f"{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return NAME_DAYS.get((p.get("first_name") or "").strip().lower(), "")


def age(p: dict, on: date | None = None) -> int | None:
    b = p.get("birthday")
    if not b or not DATE_RE.match(b):
        return None
    on = on or date.today()
    y, m, d = map(int, b.split("-"))
    return on.year - y - ((on.month, on.day) < (m, d))


def computed(p: dict) -> dict:
    return {"display_name": display_name(p), "age": age(p), "name_day": name_day(p),
            "name_day_auto": not p.get("name_day") and bool(name_day(p))}


def _next_yearly(month: int, day: int, today: date) -> date:
    for year in (today.year, today.year + 1):
        try:
            d = date(year, month, day)
        except ValueError:
            d = date(year, 2, 28)
        if d >= today:
            return d
    return date(today.year + 1, month, min(day, 28))


def reminders(days: int = 30, today: date | None = None) -> list:
    today = today or date.today()
    limit = today + timedelta(days=days)
    out = []

    def add(when: date, kind: str, p: dict, title: str) -> None:
        if today <= when <= limit:
            out.append({"date": when.isoformat(), "days": (when - today).days, "type": kind,
                        "slug": p["slug"], "person": display_name(p), "title": title})

    for p in all_profiles(light=True):
        if p.get("deceased"):
            continue
        name = display_name(p)
        if p.get("birthday") and DATE_RE.match(p["birthday"]):
            y, m, d = map(int, p["birthday"].split("-"))
            when = _next_yearly(m, d, today)
            add(when, "compleanno", p, f"Compleanno di {name} ({when.year - y} anni)")
        nd = name_day(p)
        if nd:
            d, m = map(int, nd.split("-"))
            add(_next_yearly(m, d, today), "onomastico", p, f"Onomastico di {name}")
        for e in p.get("events", []):
            if not e.get("date"):
                continue
            y, m, d = map(int, e["date"].split("-"))
            when = _next_yearly(m, d, today) if e.get("yearly") else date(y, m, d)
            label = e.get("title") or e.get("type") or "Evento"
            if e.get("yearly") and when.year > y:
                label += f" ({when.year - y}°)"
            add(when, "evento", p, f"{label} — {name}")
        for doc in p.get("documents", []):
            if doc.get("expiry"):
                add(date.fromisoformat(doc["expiry"]), "scadenza", p, f"Scadenza {doc.get('type', 'documento')} di {name}")
        for v in p.get("vehicles", []):
            for key, label in (("insurance", "assicurazione"), ("inspection", "revisione"), ("tax", "bollo")):
                if v.get(key):
                    add(date.fromisoformat(v[key]), "scadenza", p, f"Scadenza {label} {v.get('model', '')} ({name})".replace("  ", " "))
        for pet in p.get("pets", []):
            if pet.get("birthday"):
                y, m, d = map(int, pet["birthday"].split("-"))
                add(_next_yearly(m, d, today), "compleanno", p, f"Compleanno di {pet.get('name', 'animale')} ({name})")
    return sorted(out, key=lambda r: (r["date"], r["type"]))


def observe(slug: str, name: str, now: float | None = None) -> None:
    now = now or time.time()
    with _lock:
        profile = load(slug) or _blank(slugify(slug), name)
        sessions = profile.setdefault("sessions", [])
        stats = profile.setdefault("stats", {"visits": 0, "total_seconds": 0, "first_seen": None, "last_seen": None})
        if sessions and now - sessions[-1][1] <= SESSION_GAP:
            stats["total_seconds"] += max(0, now - sessions[-1][1])
            sessions[-1][1] = now
        else:
            sessions.append([now, now])
            stats["visits"] += 1
            del sessions[:-MAX_SESSIONS]
        stats["first_seen"] = stats["first_seen"] or now
        stats["last_seen"] = now
        if now - profile.get("updated_at", 0) > 30 or sessions[-1][0] == now:
            save(profile)


def habits(profile: dict) -> dict:
    sessions = profile.get("sessions") or []
    if not sessions:
        return {"summary": "Nessuna abitudine rilevata ancora.", "arrival_hours": [0] * 24,
                "weekdays": [0] * 7, "avg_minutes": 0}
    arrivals = [time.localtime(s[0]) for s in sessions]
    hours = Counter(a.tm_hour for a in arrivals)
    days = Counter(a.tm_wday for a in arrivals)
    avg = sum((s[1] - s[0]) / 60 for s in sessions) / len(sessions)
    parts = []
    if len(sessions) >= 3:
        parts.append("arriva di solito verso le " + " e le ".join(f"{h}:00" for h in sorted(h for h, _ in hours.most_common(2))))
        top_days = [DAYS_IT[d] for d, c in days.most_common(3) if c >= 2]
        if top_days:
            parts.append("soprattutto " + ", ".join(top_days))
    parts.append(f"resta in media {avg:.0f} minuti")
    return {"summary": display_name(profile) + " " + "; ".join(parts) + ".",
            "arrival_hours": [hours.get(h, 0) for h in range(24)],
            "weekdays": [days.get(d, 0) for d in range(7)], "avg_minutes": round(avg, 1)}


def context_for(slugs: list) -> str:
    today = date.today()
    upcoming = {r["slug"]: r for r in reminders(days=0, today=today)}
    lines = []
    for slug in slugs:
        p = load(slug)
        if not p or not p.get("consent", True):
            continue
        bits = [f"{display_name(p)} ({ROLES.get(p.get('role'), 'ospite')})"]
        if p.get("nickname"):
            bits.append(f"chiamalo/a {p['nickname']}")
        if age(p) is not None:
            bits.append(f"{age(p)} anni")
        if p.get("occupation"):
            bits.append(f"lavoro: {p['occupation']}")
        rels = []
        for r in p.get("relations", [])[:8]:
            other = load(r["person"]) if r.get("person") else None
            who = display_name(other) if other else r.get("name")
            if who:
                rels.append(f"{RELATIONS.get(r.get('type'), ('relazione',))[0].lower()} {who}")
        if rels:
            bits.append("relazioni: " + ", ".join(rels))
        prefs = []
        for key in ("food_likes", "drinks", "music", "movies", "sports", "hobbies"):
            if p.get(key):
                prefs.append(f"{FIELD_INDEX[key][1]['label'].lower()}: {', '.join(p[key][:5])}")
        prefs += [f"{c['key']}: {c['value']}" for c in p.get("custom", [])[:8] if c.get("key")]
        if p.get("coffee"):
            prefs.append(f"caffè: {p['coffee']}")
        if prefs:
            bits.append("preferenze: " + "; ".join(prefs))
        if p.get("share_health"):
            health = [f"allergie: {', '.join(p['allergies'])}" if p.get("allergies") else "",
                      f"dieta: {p['diet']}" if p.get("diet") else ""]
            bits += [h for h in health if h]
        if p.get("notes"):
            bits.append(f"note: {p['notes'][:300]}")
        if slug in upcoming:
            bits.append(f"OGGI: {upcoming[slug]['title']}")
        bits.append(habits(p)["summary"])
        lines.append(". ".join(bits))
    return "\n".join(lines)


def schema() -> dict:
    return {"sections": SECTIONS, "roles": ROLES}
