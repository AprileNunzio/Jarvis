import asyncio
import json
import logging
import math
import shutil
import time

import httpx

from config import DEMO, STATE_DIR, env_get, write_env

log = logging.getLogger("jarvis.location")

STATE_FILE = STATE_DIR / "location.json"
USER_AGENT = "JarvisOS/3 (+https://github.com/AprileNunzio/Jarvis)"
BROWSER_FRESH = 12 * 3600
PHONE_FRESH = 90 * 86400
WIFI_FRESH = 6 * 3600
LAN_FRESH = 7 * 86400
IP_FRESH = 6 * 3600
LAN_MAX_ACCURACY = 3000
IP_HUBS = {"milan", "milano", "rome", "roma", "frankfurt", "frankfurt am main", "amsterdam", "london", "paris",
           "arezzo", "bologna", "turin", "torino", "padova", "vienna", "zurich", "madrid", "marseille"}
PROVIDER_WEIGHT = {"ipinfo": 1.3, "ipwho.is": 1.0, "ip-api": 1.0, "freeipapi": 0.9}
MAX_TRUSTED_ACCURACY = 5000


def _load() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(data: dict) -> None:
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_FILE)


def _distance_km(a: dict, b: dict) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


class Locator:
    def __init__(self) -> None:
        self.data = _load()
        self.lock = asyncio.Lock()

    def settings(self) -> dict:
        mode = env_get("JARVIS_LOCATION_MODE", "auto")
        default = None
        try:
            lat, lon = float(env_get("JARVIS_LOCATION_LAT", "")), float(env_get("JARVIS_LOCATION_LON", ""))
            default = {"name": env_get("JARVIS_LOCATION", "") or f"{lat:.4f}, {lon:.4f}", "lat": lat, "lon": lon}
        except ValueError:
            if env_get("JARVIS_LOCATION", ""):
                default = {"name": env_get("JARVIS_LOCATION", ""), "lat": None, "lon": None}
        return {"mode": mode if mode in ("auto", "fixed") else "auto", "default": default}

    async def set_default(self, name: str, lat, lon, mode: str | None = None) -> dict:
        updates = {"JARVIS_LOCATION": (name or "").strip()[:80],
                   "JARVIS_LOCATION_LAT": "" if lat in (None, "") else f"{float(lat):.6f}",
                   "JARVIS_LOCATION_LON": "" if lon in (None, "") else f"{float(lon):.6f}"}
        if mode in ("auto", "fixed"):
            updates["JARVIS_LOCATION_MODE"] = mode
        write_env(updates)
        return await self.current(refresh=False)

    def set_mode(self, mode: str) -> None:
        if mode in ("auto", "fixed"):
            write_env({"JARVIS_LOCATION_MODE": mode})

    async def report_browser(self, lat: float, lon: float, accuracy: float) -> dict:
        return await self.report("browser", lat, lon, accuracy)

    async def report(self, source: str, lat: float, lon: float, accuracy: float) -> dict:
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Coordinate non valide")
        entry = {"lat": round(lat, 6), "lon": round(lon, 6), "accuracy": round(accuracy or 0), "at": time.time()}
        prev = self.data.get(source)
        if prev and prev.get("name") and _distance_km(prev, entry) < 1:
            entry["name"] = prev["name"]
        else:
            entry["name"] = await self._reverse(entry["lat"], entry["lon"])
        self.data[source] = entry
        _save(self.data)
        return entry

    async def _reverse(self, lat: float, lon: float) -> str:
        try:
            async with httpx.AsyncClient(timeout=8, headers={"User-Agent": USER_AGENT}) as client:
                r = await client.get("https://nominatim.openstreetmap.org/reverse",
                                     params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 16,
                                             "accept-language": "it"})
                a = r.json().get("address", {})
            city = a.get("city") or a.get("town") or a.get("village") or a.get("municipality") or a.get("county")
            street = a.get("road")
            return ", ".join(x for x in (street, city) if x) or f"{lat:.4f}, {lon:.4f}"
        except (httpx.HTTPError, ValueError):
            return f"{lat:.4f}, {lon:.4f}"

    async def _wifi(self) -> dict | None:
        cached = self.data.get("wifi")
        if cached and time.time() - cached.get("at", 0) < WIFI_FRESH:
            return cached
        if DEMO or not shutil.which("nmcli"):
            return None
        try:
            proc = await asyncio.create_subprocess_exec(
                "nmcli", "-t", "-f", "BSSID,SIGNAL", "dev", "wifi", "list", "--rescan", "auto",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
            out, _ = await asyncio.wait_for(proc.communicate(), 20)
        except (OSError, asyncio.TimeoutError):
            return None
        aps = []
        for line in out.decode(errors="replace").splitlines():
            bssid, _, signal = line.replace("\\:", "-").rpartition(":")
            if bssid and signal.isdigit():
                aps.append({"macAddress": bssid.replace("-", ":").lower(),
                            "signalStrength": int(int(signal) / 2 - 100)})
        if len(aps) < 2:
            return None
        try:
            async with httpx.AsyncClient(timeout=10, headers={"User-Agent": USER_AGENT}) as client:
                r = await client.post("https://api.beacondb.net/v1/geolocate",
                                      json={"considerIp": False, "wifiAccessPoints": aps[:40]})
            g = r.json()
            loc = {"lat": g["location"]["lat"], "lon": g["location"]["lng"], "accuracy": round(g.get("accuracy", 0)),
                   "at": time.time()}
        except (httpx.HTTPError, ValueError, KeyError):
            return None
        loc["name"] = await self._reverse(loc["lat"], loc["lon"])
        self.data["wifi"] = loc
        _save(self.data)
        return loc

    async def _geocode(self, name: str) -> dict | None:
        results = await search(name, 1)
        return results[0] if results else None

    async def _lan(self) -> dict | None:
        cached = self.data.get("lan")
        if cached and time.time() - cached.get("at", 0) < LAN_FRESH:
            return cached if cached.get("lat") is not None else None
        if DEMO:
            return None
        try:
            from features.network.explorer import explorer
            devices = list(explorer.devices.values())
        except Exception:
            return None
        macs = [d["mac"] for d in devices if d.get("mac") and d["mac"] != "self"
                and d.get("type") in ("router", "ap")]
        if not macs:
            return None
        candidates = []
        for mac in macs[:6]:
            try:
                value = int(mac.replace(":", ""), 16)
            except ValueError:
                continue
            for off in (0, 1, 2, 3, 4, 5, 6, 7, 8, -1, -2, 16, 32):
                for local in (False, True):
                    v = (value + off) & 0xFFFFFFFFFFFF
                    if local:
                        v |= 0x020000000000
                    candidates.append(":".join(f"{v:012x}"[i:i + 2] for i in range(0, 12, 2)))
        candidates = list(dict.fromkeys(candidates))[:120]
        loc = None
        try:
            async with httpx.AsyncClient(timeout=12, headers={"User-Agent": USER_AGENT}) as client:
                r = await client.post("https://api.beacondb.net/v1/geolocate", json={
                    "considerIp": False, "fallbacks": {"ipf": False, "lacf": False},
                    "wifiAccessPoints": [{"macAddress": m, "signalStrength": -55} for m in candidates]})
            if r.status_code == 200:
                g = r.json()
                if g.get("accuracy", 1e9) <= LAN_MAX_ACCURACY:
                    loc = {"lat": g["location"]["lat"], "lon": g["location"]["lng"], "accuracy": round(g["accuracy"])}
        except (httpx.HTTPError, ValueError, KeyError):
            return None
        entry = {**(loc or {"lat": None, "lon": None}), "at": time.time(), "macs": len(macs)}
        if loc:
            entry["name"] = await self._reverse(loc["lat"], loc["lon"])
            log.info("Posizione dalla rete di casa: %s (±%d m)", entry["name"], loc["accuracy"])
        self.data["lan"] = entry
        _save(self.data)
        return entry if loc else None

    async def _ip(self) -> dict | None:
        cached = self.data.get("ip")
        if cached and time.time() - cached.get("at", 0) < IP_FRESH:
            return cached

        async def probe(client, name, url, parse):
            try:
                r = await client.get(url)
                lat, lon, city = parse(r.json())
                return {"provider": name, "lat": float(lat), "lon": float(lon), "city": city or ""}
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                return None

        async with httpx.AsyncClient(timeout=8, headers={"User-Agent": USER_AGENT}) as client:
            results = await asyncio.gather(
                probe(client, "ip-api", "http://ip-api.com/json/?fields=city,lat,lon", lambda g: (g["lat"], g["lon"], g.get("city"))),
                probe(client, "ipwho.is", "https://ipwho.is/", lambda g: (g["latitude"], g["longitude"], g.get("city"))),
                probe(client, "ipinfo", "https://ipinfo.io/json", lambda g: (*g["loc"].split(","), g.get("city"))),
                probe(client, "freeipapi", "https://freeipapi.com/api/json", lambda g: (g["latitude"], g["longitude"], g.get("cityName"))),
            )
        points = [p for p in results if p]
        if not points:
            return cached

        def is_hub(p):
            return p["city"].lower() in IP_HUBS

        specific = [p for p in points if not is_hub(p)]
        pool = specific if specific and len(specific) < len(points) else points
        best = min(pool, key=lambda p: sum(_distance_km(p, q) * PROVIDER_WEIGHT.get(q["provider"], 1) for q in pool)
                   - PROVIDER_WEIGHT.get(p["provider"], 1))
        spread_km = max((_distance_km(best, q) for q in points), default=50)
        cities = {}
        for p in points:
            cities.setdefault(p["city"] or "?", []).append(p["provider"])
        it = await self._geocode(best["city"]) if best["city"] else None
        loc = {"name": (it or {}).get("name", best["city"] or "posizione approssimata"), "lat": best["lat"],
               "lon": best["lon"], "accuracy": int(max(25000, min(spread_km, 800) * 1000)), "at": time.time(),
               "providers": [{"provider": p["provider"], "city": p["city"]} for p in points], "approximate": True,
               "disagree": len(cities) > 1, "cities": [{"city": c, "providers": v} for c, v in cities.items()]}
        self.data["ip"] = loc
        _save(self.data)
        return loc

    async def current(self, refresh: bool = True) -> dict:
        async with self.lock:
            s = self.settings()
            default = s["default"]
            if default and default.get("lat") is None:
                geo = await self._geocode(default["name"])
                default = {**geo, "name": default["name"]} if geo else None
            now = time.time()
            candidates = []
            if s["mode"] == "auto":
                ph = self.data.get("phone")
                if ph and now - ph.get("at", 0) < PHONE_FRESH:
                    candidates.append(("phone", ph))
                b = self.data.get("browser")
                if b and now - b.get("at", 0) < BROWSER_FRESH and (b.get("accuracy") or 0) <= MAX_TRUSTED_ACCURACY:
                    candidates.append(("browser", b))
                if refresh:
                    w = await self._wifi()
                    if w:
                        candidates.append(("wifi", w))
                    lan = await self._lan()
                    if lan:
                        candidates.append(("lan", lan))
            if default:
                candidates.append(("default", {**default, "accuracy": None}))
            if s["mode"] == "auto" and refresh:
                ip = await self._ip()
                if ip:
                    candidates.append(("ip", ip))
            if not candidates:
                return {"name": "posizione sconosciuta", "lat": None, "lon": None, "source": "none", "mode": s["mode"]}
            source, loc = candidates[0]
            return {"name": loc.get("name"), "lat": loc["lat"], "lon": loc["lon"], "accuracy": loc.get("accuracy"),
                    "source": source, "mode": s["mode"], "at": loc.get("at"), "approximate": source == "ip"}

    def overview(self) -> dict:
        return {"settings": self.settings(), "sources": {k: v for k, v in self.data.items()}}


async def search(query: str, count: int = 6) -> list:
    query = (query or "").strip()
    if len(query) < 2:
        return []
    out = []
    async with httpx.AsyncClient(timeout=8, headers={"User-Agent": USER_AGENT}) as client:
        if not any(c.isdigit() for c in query) and "," not in query:
            r = await client.get("https://geocoding-api.open-meteo.com/v1/search",
                                 params={"name": query, "count": count, "language": "it"})
            for g in r.json().get("results") or []:
                region = ", ".join(x for x in (g.get("admin1"), g.get("country")) if x)
                out.append({"name": g["name"], "detail": region, "lat": g["latitude"], "lon": g["longitude"]})
        if not out:
            r = await client.get("https://nominatim.openstreetmap.org/search",
                                 params={"q": query, "format": "jsonv2", "limit": count, "accept-language": "it"})
            for g in r.json():
                name, _, detail = g.get("display_name", query).partition(", ")
                out.append({"name": name, "detail": detail[:90], "lat": float(g["lat"]), "lon": float(g["lon"])})
    return out


locator = Locator()
