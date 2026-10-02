import asyncio
import json
import logging
import re
import time
import urllib.parse
from datetime import datetime, timedelta

import httpx

from config import STATE_DIR, env_get
from state import store

from features.maps import personal

log = logging.getLogger("jarvis.maps")

STATE_FILE = STATE_DIR / "maps.json"
MODES = {"drive": ("DRIVE", "in auto", "driving"), "walk": ("WALK", "a piedi", "walking"),
         "bike": ("BICYCLE", "in bici", "bicycling"), "transit": ("TRANSIT", "con i mezzi", "transit"),
         "moto": ("TWO_WHEELER", "in moto", "driving")}
DAYS_IT = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]


def _fmt_min(minutes: float) -> str:
    m = max(1, round(minutes))
    if m < 60:
        return f"{m} minut{'o' if m == 1 else 'i'}"
    h, r = divmod(m, 60)
    return f"{h} or{'a' if h == 1 else 'e'}" + (f" e {r} minuti" if r else "")


def _fmt_km(meters: float) -> str:
    return f"{meters / 1000:.1f} km".replace(".", ",") if meters >= 1000 else f"{round(meters)} m"


class Maps:
    def __init__(self) -> None:
        self.data = self._load()
        self.status = "pronto"
        self.announced: dict[str, float] = {}

    @staticmethod
    def _load() -> dict:
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"places": {}}

    def _save(self) -> None:
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(STATE_FILE)

    @staticmethod
    def enabled() -> bool:
        return env_get("JARVIS_MAPS", "1") != "0"

    @staticmethod
    def key() -> str:
        return env_get("JARVIS_MAPS_API_KEY", "").strip()

    @staticmethod
    def default_mode() -> str:
        m = env_get("JARVIS_MAPS_MODE", "drive")
        return m if m in MODES else "drive"

    async def home(self) -> dict:
        from features.location.locator import locator
        loc = await locator.current()
        if loc.get("lat") is None:
            raise ValueError("non so ancora dove si trova casa: dimmi «abito a …»")
        return {"name": "casa", "label": loc.get("name") or "casa", "lat": loc["lat"], "lon": loc["lon"]}

    def place(self, name: str) -> dict | None:
        return self.data.get("places", {}).get(name.lower().strip())

    async def save_place(self, name: str, address: str) -> dict:
        from features.location.locator import search
        found = await search(address, 1)
        if not found:
            raise LookupError(address)
        p = {"name": name.lower(), "label": address, "lat": found[0]["lat"], "lon": found[0]["lon"],
             "detail": found[0].get("detail", "")}
        self.data.setdefault("places", {})[p["name"]] = p
        self._save()
        store.event("INFO", f"Maps: luogo «{name}» salvato ({address})", "maps")
        return p

    def delete_place(self, name: str) -> None:
        self.data.get("places", {}).pop(name.lower(), None)
        self._save()

    async def geocode(self, name: str, text: str) -> dict:
        cache = self.data.setdefault("geo", {})
        if text not in cache:
            from features.location.locator import search
            found = await search(text, 1)
            if not found:
                raise LookupError(text)
            cache[text] = {"lat": found[0]["lat"], "lon": found[0]["lon"], "detail": found[0].get("detail", "")}
            self._save()
        return {"name": name, "label": text, **cache[text]}

    async def personal_place(self, what: str, profile: dict | None = None) -> dict | None:
        label = personal.kind_of(what)
        who = profile or personal.current()
        if not label or label == "Casa" or not who:
            return None
        text = personal.address(who, label)
        return await self.geocode(what.lower(), text) if text else None

    async def resolve(self, what: str) -> dict:
        w = re.sub(r"^(?:all'|allo|alla|al|ad|il|lo|la|l'|in|a)\s+|^(?:all'|l')", "", what.strip(), flags=re.I).strip(" ?!.")
        if w.lower() in ("casa", "a casa", "home"):
            return await self.home()
        mine = await self.personal_place(w)
        if mine:
            return mine
        for alias, name in (("ufficio", "lavoro"), ("lavoro", "lavoro")):
            if w.lower() == alias and self.place(name):
                return self.place(name)
        if self.place(w):
            return self.place(w)
        if self.key():
            return {"name": w, "label": w, "address": w}
        from features.location.locator import search
        found = await search(w, 1)
        if not found:
            raise LookupError(w)
        label = w[0].upper() + w[1:]
        detail = ", ".join(x for x in (found[0]["name"], found[0].get("detail", "")) if x)
        return {"name": w, "label": label, "detail": detail,
                "lat": found[0]["lat"], "lon": found[0]["lon"]}

    async def route(self, origin: dict, dest: dict, mode: str = "drive", arrive_by: datetime | None = None) -> dict:
        if self.key():
            try:
                return await self._google(origin, dest, mode, arrive_by)
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                log.warning("Routes API: %s — uso OpenStreetMap", exc)
                self.status = f"Google non disponibile: {exc}"[:160]
        if "lat" not in dest:
            from features.location.locator import search
            found = await search(dest["label"], 1)
            if not found:
                raise LookupError(dest["label"])
            dest = {**dest, "lat": found[0]["lat"], "lon": found[0]["lon"]}
        return await self._osrm(origin, dest, "drive" if mode in ("transit", "moto") else mode)

    @staticmethod
    def _wp(p: dict) -> dict:
        if "lat" in p:
            return {"location": {"latLng": {"latitude": p["lat"], "longitude": p["lon"]}}}
        return {"address": p.get("address") or p["label"]}

    async def _google(self, origin: dict, dest: dict, mode: str, arrive_by: datetime | None) -> dict:
        travel = MODES[mode][0]
        body = {"origin": self._wp(origin), "destination": self._wp(dest), "travelMode": travel,
                "languageCode": "it", "units": "METRIC", "computeAlternativeRoutes": False}
        if travel in ("DRIVE", "TWO_WHEELER"):
            body["routingPreference"] = "TRAFFIC_AWARE_OPTIMAL"
            body["extraComputations"] = ["TRAFFIC_ON_POLYLINE"]
        if arrive_by and travel == "TRANSIT":
            body["arrivalTime"] = arrive_by.astimezone().isoformat()
        fields = ("routes.duration,routes.staticDuration,routes.distanceMeters,routes.description,"
                  "routes.warnings,routes.travelAdvisory.tollInfo,routes.localizedValues,"
                  "routes.legs.steps.navigationInstruction,routes.legs.steps.distanceMeters,"
                  "routes.legs.steps.transitDetails,routes.legs.endLocation,routes.legs.startLocation,"
                  "routes.polyline.encodedPolyline")
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post("https://routes.googleapis.com/directions/v2:computeRoutes", json=body,
                                  headers={"X-Goog-Api-Key": self.key(), "X-Goog-FieldMask": fields})
        data = r.json()
        if r.status_code != 200:
            raise ValueError((data.get("error") or {}).get("message", f"errore {r.status_code}"))
        if not data.get("routes"):
            raise LookupError(dest.get("label", ""))
        rt = data["routes"][0]
        secs = int(rt["duration"].rstrip("s"))
        base = int(rt.get("staticDuration", rt["duration"]).rstrip("s"))
        steps = []
        for leg in rt.get("legs", []):
            for st in leg.get("steps", []):
                ins = (st.get("navigationInstruction") or {}).get("instructions", "")
                td = st.get("transitDetails")
                if td:
                    line = (td.get("transitLine") or {})
                    ins = (f"{line.get('vehicle', {}).get('name', {}).get('text', 'Linea')} "
                           f"{line.get('nameShort') or line.get('name', '')} da {td['stopDetails']['departureStop']['name']} "
                           f"a {td['stopDetails']['arrivalStop']['name']} ({td.get('stopCount', '?')} fermate)")
                if ins:
                    steps.append({"text": ins.replace("\n", " "), "dist": st.get("distanceMeters", 0)})
        path = _decode((rt.get("polyline") or {}).get("encodedPolyline", ""))
        return {"engine": "google", "path": _thin(path), "mode": mode, "minutes": secs / 60, "base_minutes": base / 60,
                "delay_minutes": max(0, (secs - base) / 60), "meters": rt.get("distanceMeters", 0),
                "via": rt.get("description", ""), "warnings": rt.get("warnings", []),
                "tolls": bool((rt.get("travelAdvisory") or {}).get("tollInfo")), "steps": steps}

    async def _osrm(self, origin: dict, dest: dict, mode: str) -> dict:
        profile = {"drive": "driving", "walk": "foot", "bike": "bike"}[mode]
        host = {"driving": "router.project-osrm.org/route/v1/driving",
                "foot": "routing.openstreetmap.de/routed-foot/route/v1/foot",
                "bike": "routing.openstreetmap.de/routed-bike/route/v1/bike"}[profile]
        url = f"https://{host}/{origin['lon']},{origin['lat']};{dest['lon']},{dest['lat']}"
        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": "JarvisOS/3"}) as client:
            r = await client.get(url, params={"overview": "full", "geometries": "geojson", "steps": "true"})
        data = r.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            raise LookupError(dest.get("label", ""))
        rt = data["routes"][0]
        steps, roads = [], []
        for leg in rt.get("legs", []):
            for st in leg.get("steps", []):
                text = _osrm_text(st)
                if text:
                    steps.append({"text": text, "dist": st.get("distance", 0)})
                if st.get("name") and st.get("distance", 0) > 1500 and st["name"] not in roads:
                    roads.append(st["name"])
        path = [[c[1], c[0]] for c in (rt.get("geometry") or {}).get("coordinates", [])]
        return {"engine": "osm", "path": _thin(path), "mode": mode, "minutes": rt["duration"] / 60, "base_minutes": rt["duration"] / 60,
                "delay_minutes": None, "meters": rt["distance"], "via": ", ".join(roads[:2]), "warnings": [],
                "tolls": False, "steps": steps}

    @staticmethod
    def link(origin: dict, dest: dict, mode: str) -> str:
        fmt = lambda p: f"{p['lat']},{p['lon']}" if "lat" in p else (p.get("address") or p["label"])
        return "https://www.google.com/maps/dir/?api=1&" + urllib.parse.urlencode(
            {"origin": fmt(origin), "destination": fmt(dest), "travelmode": MODES[mode][2]})

    def card(self, origin: dict, dest: dict, r: dict, arrive: datetime | None = None, title: str = "") -> dict:
        now = datetime.now()
        leave = (arrive - timedelta(minutes=r["minutes"] + 5)).strftime("%H:%M") if arrive else ""
        return {"title": title or f"Verso {dest['label']}", "from": origin.get("label", "casa"), "to": dest["label"],
                "to_detail": dest.get("detail", "")[:90],
                "mode": MODES[r["mode"]][1], "minutes": round(r["minutes"]), "duration": _fmt_min(r["minutes"]),
                "delay": round(r["delay_minutes"]) if r["delay_minutes"] is not None else None,
                "distance": _fmt_km(r["meters"]), "via": r["via"], "tolls": r["tolls"],
                "arrive_at": arrive.strftime("%H:%M") if arrive else (now + timedelta(minutes=r["minutes"])).strftime("%H:%M"),
                "leave_by": leave, "traffic": r["engine"] == "google",
                "steps": [f"{s['text']} ({_fmt_km(s['dist'])})" if s["dist"] else s["text"] for s in r["steps"][:12]],
                "link": self.link(origin, dest, r["mode"]), "path": r.get("path") or [],
                "a": [origin["lat"], origin["lon"]] if origin.get("lat") is not None else None,
                "b": [dest["lat"], dest["lon"]] if dest.get("lat") is not None else None}

    async def _commute(self) -> None:
        for profile in personal.present():
            plan = personal.commute(profile)
            work = await self.personal_place("lavoro", profile) if plan else None
            if plan and work:
                await self._commute_for(profile, plan, work)

    async def _commute_for(self, profile: dict, plan: dict, work: dict) -> None:
        now = datetime.now()
        lo, hi = plan["days"]
        if not (lo <= now.isoweekday() <= hi):
            return
        leave = now.replace(hour=plan["hour"], minute=plan["minute"], second=0, microsecond=0)
        if not (leave - timedelta(minutes=plan["before"]) <= now <= leave + timedelta(minutes=10)):
            return
        key = f"commute:{profile['slug']}:{now.date()}"
        if key in self.announced:
            return
        self.announced[key] = time.time()
        mode = plan["mode"] if plan["mode"] in MODES else self.default_mode()
        origin = await self.home()
        r = await self.route(origin, work, mode)
        name = profile.get("nickname") or profile.get("first_name") or profile.get("name") or ""
        data = self.card(origin, work, r, title=f"{name}, verso il lavoro" if name else "Verso il lavoro")
        delay = f", con {r['delay_minutes']:.0f} minuti di traffico" if (r["delay_minutes"] or 0) >= 3 else ""
        data["speak"] = (f"Buongiorno{' ' + name if name else ''}. Per andare al lavoro oggi ci vogliono "
                         f"{_fmt_min(r['minutes'])}{delay}. Se esci alle {leave:%H:%M} arrivi verso le "
                         f"{(leave + timedelta(minutes=r['minutes'])):%H:%M}.")
        data["announce"] = True
        from features.desktop.desk import desk
        desk.show("route", data, key=f"route:commute:{profile['slug']}",
                  ttl=max(600, (leave - now).total_seconds() + 900))
        store.event("INFO", f"Tragitto per il lavoro di {name}: {_fmt_min(r['minutes'])}", "maps")

    async def _events(self) -> None:
        from features.google.gservices import google
        horizon = int(env_get("JARVIS_MAPS_EVENT_HOURS", "4") or 4)
        now = datetime.now().astimezone()
        events = []
        for _, session in google.present_sessions("calendar"):
            events += [e for e in await session.events(now, now + timedelta(hours=horizon), 10)
                       if e["where"] and not e["all_day"]]
        if not events:
            return
        origin = await self.home()
        from features.desktop.desk import desk
        for e in events:
            last = self.announced.get(f"event:{e['id']}", 0)
            if time.time() - last < 3600:
                continue
            try:
                dest = await self.resolve(e["where"])
                r = await self.route(origin, dest, self.default_mode())
            except (LookupError, httpx.HTTPError, ValueError) as exc:
                log.info("Percorso per «%s» non calcolato: %s", e["title"], exc)
                self.announced[f"event:{e['id']}"] = time.time()
                continue
            start = e["start"].replace(tzinfo=None)
            leave = start - timedelta(minutes=r["minutes"] + 5)
            if (leave - datetime.now()).total_seconds() > 90 * 60:
                continue
            self.announced[f"event:{e['id']}"] = time.time()
            data = self.card(origin, dest, r, arrive=start, title=e["title"])
            late = leave < datetime.now()
            data["speak"] = (f"Ricorda: alle {start:%H:%M} ha {e['title']}. Ci vogliono {_fmt_min(r['minutes'])}"
                             + (f", con {r['delay_minutes']:.0f} minuti di traffico" if (r["delay_minutes"] or 0) >= 3 else "")
                             + ("; è già in ritardo, conviene partire subito." if late
                                else f"; parta entro le {leave:%H:%M}."))
            data["announce"] = True
            desk.show("route", data, key=f"route:event:{e['id']}",
                      ttl=max(600, (start - datetime.now()).total_seconds()))
            store.event("INFO", f"Avviso viaggio: {e['title']} (parti entro le {leave:%H:%M})", "maps")
        self.announced = {k: v for k, v in self.announced.items() if time.time() - v < 86400}

    def summary(self) -> dict:
        return {"enabled": self.enabled(), "engine": "google" if self.key() else "osm", "has_key": bool(self.key()),
                "status": self.status, "places": list(self.data.get("places", {}).values()),
                "people": personal.overview(), "mode": self.default_mode()}

    async def run(self) -> None:
        if not self.data.get("migrated") and personal.migrate(self.data.get("places", {})):
            self.data.get("places", {}).pop("lavoro", None)
            self.data["migrated"] = True
            self._save()
        while True:
            await asyncio.sleep(60)
            if not self.enabled():
                continue
            try:
                await self._commute()
                await self._events()
            except Exception as exc:
                log.warning("Avvisi di viaggio: %s", exc)


def _thin(path: list, limit: int = 400) -> list:
    if len(path) <= limit:
        return [[round(a, 5), round(b, 5)] for a, b in path]
    step = len(path) / limit
    out = [path[int(i * step)] for i in range(limit)] + [path[-1]]
    return [[round(a, 5), round(b, 5)] for a, b in out]


def _decode(encoded: str) -> list:
    points, index, lat, lon = [], 0, 0, 0
    while index < len(encoded):
        values = []
        for _ in range(2):
            shift = result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            values.append(~(result >> 1) if result & 1 else result >> 1)
        lat += values[0]
        lon += values[1]
        points.append([lat / 1e5, lon / 1e5])
    return points


def _osrm_text(st: dict) -> str:
    man = st.get("maneuver", {})
    kind, mod, name = man.get("type", ""), man.get("modifier", ""), st.get("name", "")
    side = {"left": "a sinistra", "right": "a destra", "slight left": "leggermente a sinistra",
            "slight right": "leggermente a destra", "sharp left": "tutto a sinistra", "sharp right": "tutto a destra",
            "straight": "dritto", "uturn": "con un'inversione"}.get(mod, "")
    on = f" su {name}" if name else ""
    if kind == "depart":
        return f"Parti{on}"
    if kind == "arrive":
        return "Sei arrivato a destinazione"
    if kind in ("roundabout", "rotary"):
        return f"Alla rotonda prendi la {man.get('exit', 1)}ª uscita{on}"
    if kind in ("turn", "end of road", "fork", "on ramp", "off ramp") and side:
        return f"Svolta {side}{on}" if kind != "on ramp" else f"Entra {side}{on}"
    if kind == "merge":
        return f"Immettiti{on}"
    if kind in ("continue", "new name") and name:
        return f"Continua{on}"
    return ""


maps = Maps()


_ROUTE_RE = re.compile(
    r"\b(?:come (?:arrivo|si arriva|ci arrivo|vado|raggiungo|faccio ad andare)|indicazioni(?: stradali)?|"
    r"(?:la )?strada (?:per|verso)|percorso (?:per|verso)|portami|navigatore|"
    r"quanto (?:ci )?(?:metto|tempo ci vuole|ci vuole|dista|è lontan[oa])|quanti (?:minuti|km|chilometri)|"
    r"(?:c'è|com'è il|quanto) traffico|tempo di (?:viaggio|percorrenza))\b", re.I)
_DEST_RE = re.compile(r"\b(?:per|verso|fino)\s+(?:(?:andare|arrivare)\s+)?(?:all'|allo|alla|al|ad|a|in)?\s*"
                      r"|\b(?:allo|alla|al|ad|a|in)\s+|\ball'", re.I)
_FROM_RE = re.compile(r"\bda\s+(.+?)\s+(?:a|ad|al|alla|allo|all'|in|fino a)\s+(.+)$", re.I)
_SAVE_RE = re.compile(r"\b(?:il mio (lavoro|ufficio)|(?:io )?lavoro)\s+(?:è|e'|si trova|sta)?\s*(?:in|a|ad|al|presso)\s+(.{4,})$"
                      r"|\bsalva\s+(.{4,}?)\s+come\s+([\wÀ-ÿ' ]{2,30})$"
                      r"|\b(?:la mia |il mio )?(palestra|scuola|università|ufficio|lavoro)\s+(?:è|e'|si trova)\s+(?:in|a|al)\s+(.{4,})$",
                      re.I)
_COMMUTE_RE = re.compile(r"\b(?:esco|parto|vado)(?: di casa)? (?:per andare |per |a )?(?:al |a )?lavoro(?: ogni mattina| la mattina)?"
                         r" (?:alle|verso le)\s+|\b(?:esco|parto) (?:di casa )?(?:alle|verso le) .{0,10}(?:per|a)(?: andare)?(?: al)? lavoro",
                         re.I)
_MODE_WORDS = [("walk", r"\ba piedi\b|\bcamminando\b"), ("bike", r"\bin bici(?:cletta)?\b"),
               ("transit", r"\bcon i mezzi\b|\bin (?:autobus|bus|metro|treno|metropolitana)\b|\bmezzi pubblici\b"),
               ("moto", r"\bin moto(?:rino)?\b|\bin scooter\b"), ("drive", r"\bin (?:auto|macchina)\b")]


def _mode(text: str) -> str:
    for m, rx in _MODE_WORDS:
        if re.search(rx, text, re.I):
            return m
    return maps.default_mode()


def _clean_dest(s: str) -> str:
    s = re.sub(r"\b(?:a piedi|camminando|in bici(?:cletta)?|con i mezzi|in (?:autobus|bus|metro|treno|metropolitana|"
               r"auto|macchina|moto(?:rino)?|scooter)|mezzi pubblici|adesso|ora|oggi|domani|stasera|subito|"
               r"con il traffico|c'è traffico)\b", " ", s, flags=re.I)
    return re.sub(r"\s{2,}", " ", s).strip(" ?!.,")


async def answer(text: str) -> tuple[str, dict]:
    if not maps.enabled():
        raise LookupError
    m = _COMMUTE_RE.search(text)
    if m:
        from features.google.timeparse import parse_time
        hm, _ = parse_time(text[m.start():], assume_pm=False)
        if hm:
            h, mi = hm
            who = personal.current()
            if not who:
                return ("Non so ancora chi è, signore: si metta davanti alla webcam o crei la sua scheda in Persone, "
                        "così salvo il tragitto solo per lei.", {"mode": "face"})
            personal.set_commute(who, h, mi)
            hint = "" if personal.address(who, "Lavoro") else \
                " Mi dica anche dove lavora, per esempio «il mio lavoro è in via Toledo 10, Napoli»."
            return (f"Perfetto{', ' + who.get('first_name') if who.get('first_name') else ''}: nei giorni feriali verso "
                    f"le {h:02d}:{mi:02d} le mostrerò il tragitto per il lavoro con il traffico, quando la vedo "
                    f"davanti allo schermo. L'ho salvato nella sua scheda.{hint}", {"mode": "face"})
    m = _SAVE_RE.search(text.strip(" .!"))
    if m:
        if m.group(3):
            addr, name = m.group(3), m.group(4)
        elif m.group(5):
            name, addr = m.group(5), m.group(6)
        else:
            name, addr = "lavoro", m.group(2)
        name = "lavoro" if name.lower() in ("ufficio", "lavoro") else name.lower().strip()
        label, who = personal.kind_of(name), personal.current()
        try:
            if label and label != "Casa" and who:
                p = await maps.geocode(name, addr.strip())
                personal.save_address(who, label, addr.strip())
            else:
                p = await maps.save_place(name, addr.strip())
        except LookupError:
            return f"Non trovo l'indirizzo «{addr}». Puoi ripeterlo con la città?", {"mode": "face"}
        return (f"Ho salvato {name}: {p['label']}{', ' + p['detail'] if p.get('detail') else ''}. "
                f"Chiedimi pure «quanto ci metto ad andare {'al lavoro' if name == 'lavoro' else 'a ' + name}».",
                {"mode": "face"})
    if not _ROUTE_RE.search(text):
        raise LookupError
    mode = _mode(text)
    f = _FROM_RE.search(text)
    if f:
        origin, dest_txt = await maps.resolve(f.group(1)), _clean_dest(f.group(2))
    else:
        origin = await maps.home()
        after = _ROUTE_RE.split(text, maxsplit=1)[-1]
        dm = _DEST_RE.search(after)
        dest_txt = _clean_dest(after[dm.end():] if dm else after)
        if not dest_txt and re.search(r"\blavoro\b", text, re.I):
            dest_txt = "lavoro"
    dest_txt = re.sub(r"^(?:andare|arrivare)\s+(?:all'|allo|alla|al|ad|a|in)?\s*", "", dest_txt, flags=re.I)
    if not dest_txt or len(dest_txt) < 2:
        return "Dove desidera andare, signore?", {"mode": "face"}
    if dest_txt.lower() in ("lavoro", "ufficio") and not await maps.personal_place("lavoro"):
        return ("Non so ancora dove lavori: dimmi per esempio «il mio lavoro è in via Toledo 10, Napoli».",
                {"mode": "face"})
    try:
        dest = await maps.resolve(dest_txt)
        r = await maps.route(origin, dest, mode)
    except LookupError:
        return f"Non trovo «{dest_txt}» sulla mappa. Puoi dirmi anche la città?", {"mode": "face"}
    data = maps.card(origin, dest, r)
    traffic = ""
    if r["delay_minutes"] is not None and r["mode"] in ("drive", "moto"):
        traffic = (f" C'è traffico: {round(r['delay_minutes'])} minuti in più del solito." if r["delay_minutes"] >= 3
                   else " Il traffico è scorrevole.")
    speech = (f"Per {dest['label']} {MODES[r['mode']][1]} ci vogliono {_fmt_min(r['minutes'])}, "
              f"{_fmt_km(r['meters'])}" + (f", passando per {r['via']}" if r["via"] else "") + "." + traffic
              + f" Se parti ora arrivi alle {data['arrive_at']}.")
    if r["engine"] == "osm" and r["mode"] in ("drive", "moto"):
        speech += " Il tempo è stimato senza traffico."
    if mode == "transit" and r["engine"] == "osm":
        speech = "Per i mezzi pubblici mi serve la chiave di Google Maps. Intanto, in auto: " + speech
    panels = [{"type": "routemap", "title": "", "data": data}]
    return speech, {"mode": "focus", "title": data["title"], "subtitle": f"{data['from']} → {data['to']}",
                    "panels": panels}
