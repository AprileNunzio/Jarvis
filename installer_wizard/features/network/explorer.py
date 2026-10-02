import asyncio
import ipaddress
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter

import httpx

from config import DEMO, STATE_DIR, env_get
from state import store

log = logging.getLogger("jarvis.network")
DEVICES_FILE = STATE_DIR / "devices.json"
SCAN_EVERY = 10 * 60
RESTUDY_EVERY = 7 * 24 * 3600
MAX_SESSIONS = 300

TYPES = {
    "router": ("Router / gateway", "📡"), "ap": ("Access point / rete", "📶"), "phone": ("Smartphone / tablet", "📱"),
    "computer": ("Computer", "💻"), "server": ("Server", "🖥"), "printer": ("Stampante", "🖨"), "tv": ("TV / media", "📺"),
    "camera": ("Telecamera", "📷"), "nas": ("NAS / archivio", "🗄"), "iot": ("Dispositivo IoT", "🔌"),
    "esp": ("ESP32 / ESP8266", "🔧"), "raspberry": ("Raspberry Pi", "🍓"), "speaker": ("Altoparlante / assistente", "🔊"),
    "homeassistant": ("Home Assistant", "🏠"), "console": ("Console di gioco", "🎮"), "jarvis": ("Questo Jarvis", "🤖"),
    "unknown": ("Sconosciuto", "❔"),
}
VENDOR_RULES = [
    (r"ubiquiti|aruba|ruckus|eero|tp-link.*deco", "ap"), (r"proxmox|vmware|supermicro", "server"),
    (r"wiz|signify|philips lighting|lifx|nanoleaf", "iot"), (r"nvidia", "tv"),
    (r"espressif", "esp"), (r"raspberry", "raspberry"), (r"synology|qnap|western digital|seagate", "nas"),
    (r"hikvision|dahua|reolink|axis|ezviz|foscam|amcrest|uniview", "camera"),
    (r"hewlett|hp inc|epson|canon|brother|lexmark|kyocera|xerox|ricoh", "printer"),
    (r"sonos|bose|harman", "speaker"), (r"amazon", "speaker"), (r"google|nest", "tv"),
    (r"roku|lg electronics|vizio|hisense|tcl|philips|panasonic|sony", "tv"),
    (r"nintendo|sony interactive|microsoft.*xbox", "console"),
    (r"tp-link|netgear|mikrotik|avm|fritz|zyxel|d-link|linksys|huawei tech|technicolor|sagemcom|arris", "router"),
    (r"apple|samsung|xiaomi|oneplus|oppo|motorola|realme|vivo|honor", "phone"),
    (r"intel|dell|lenovo|asustek|micro-star|gigabyte|hewlett packard enterprise|acer", "computer"),
    (r"tuya|shelly|sonoff|itead|meross|broadlink|lifx|signify|yeelight|aqara|lumi", "iot"),
]
PORT_RULES = [({8123}, "homeassistant"), ({6053}, "esp"), ({9100, 631, 515}, "printer"), ({554, 8554}, "camera"),
              ({5000, 5001}, "nas"), ({8008, 8009}, "tv"), ({3000, 3001, 8001, 8002}, "tv"), ({1883, 8883}, "server"),
              ({445, 139, 3389}, "computer"), ({22}, "server"), ({62078}, "phone")]
MDNS_RULES = [("_ipp", "printer"), ("_printer", "printer"), ("_googlecast", "tv"), ("_airplay", "tv"),
              ("_raop", "speaker"), ("_esphomelib", "esp"), ("_home-assistant", "homeassistant"), ("_hap", "iot"),
              ("_smb", "nas"), ("_sonos", "speaker"), ("_amzn", "speaker"), ("_companion-link", "phone")]


async def sh(*cmd: str, timeout: float = 300) -> tuple[int, str]:
    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.DEVNULL)
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
        return proc.returncode or 0, out.decode("utf-8", "replace")
    except (OSError, asyncio.TimeoutError) as exc:
        return 1, str(exc)


class NetworkExplorer:
    def __init__(self) -> None:
        self.devices: dict = self._load()
        self.subnet = ""
        self.gateway = ""
        self.own_ip = ""
        self.scanning = False
        self.last_scan = 0.0
        self.queue: asyncio.Queue | None = None
        self.on_new_device = None
        self.on_device_learned = None

    def _load(self) -> dict:
        try:
            return json.loads(DEVICES_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def save(self) -> None:
        tmp = DEVICES_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.devices, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(DEVICES_FILE)

    async def detect_subnet(self) -> None:
        _, route = await sh("ip", "-4", "route", "show", "default", timeout=10)
        m = re.search(r"default via (\S+) dev (\S+)", route)
        if not m:
            return
        self.gateway, dev = m.group(1), m.group(2)
        _, addr = await sh("ip", "-4", "-o", "addr", "show", "dev", dev, timeout=10)
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)/(\d+)", addr)
        if m:
            self.own_ip = m.group(1)
            prefix = max(24, int(m.group(2)))
            self.subnet = str(ipaddress.ip_network(f"{m.group(1)}/{prefix}", strict=False))

    def classify(self, d: dict) -> str:
        if d.get("type_manual"):
            return d["type"]
        if d.get("ip") == self.own_ip:
            return "jarvis"
        if d.get("ip") == self.gateway:
            return "router"
        ports = {p["port"] for p in d.get("ports", [])}
        for wanted, kind in PORT_RULES[:2]:
            if ports & wanted:
                return kind
        for service in d.get("mdns", []):
            for key, kind in MDNS_RULES:
                if key in service:
                    return kind
        vendor = (d.get("vendor") or "").lower()
        for pattern, kind in VENDOR_RULES:
            if re.search(pattern, vendor):
                return kind
        for wanted, kind in PORT_RULES[2:]:
            if ports & wanted:
                return kind
        os_name = (d.get("os") or "").lower()
        if "android" in os_name or "ios" in os_name:
            return "phone"
        if "windows" in os_name or "mac os" in os_name:
            return "computer"
        if "linux" in os_name:
            return "server"
        return "unknown"

    async def discover(self) -> list:
        if DEMO:
            return []
        if not self.subnet:
            await self.detect_subnet()
        if not self.subnet:
            return []
        code, xml = await sh("nmap", "-sn", "-PR", "-n", "--max-retries", "1", "-oX", "-", self.subnet, timeout=180)
        found = []
        if code == 0 and xml:
            for host in ET.fromstring(xml).findall("host"):
                if host.find("status").get("state") != "up":
                    continue
                entry = {"ip": None, "mac": None, "vendor": ""}
                for a in host.findall("address"):
                    if a.get("addrtype") == "ipv4":
                        entry["ip"] = a.get("addr")
                    elif a.get("addrtype") == "mac":
                        entry["mac"], entry["vendor"] = a.get("addr").lower(), a.get("vendor") or ""
                if entry["ip"] == self.own_ip and not entry["mac"]:
                    entry["mac"] = "self"
                if entry["ip"]:
                    found.append(entry)
        _, names = await sh("avahi-browse", "-aprt", timeout=15)
        mdns: dict = {}
        for line in names.splitlines():
            parts = line.split(";")
            if len(parts) > 8 and parts[0] == "=" and parts[2] == "IPv4":
                mdns.setdefault(parts[7], {"services": set(), "host": parts[6]})["services"].add(parts[4])
        for entry in found:
            info = mdns.get(entry["ip"])
            if info:
                entry["hostname"] = info["host"]
                entry["mdns"] = sorted(info["services"])
        return found

    async def scan(self) -> dict:
        if self.scanning:
            return {"status": "già in corso"}
        self.scanning = True
        now = time.time()
        try:
            found = await self.discover()
            seen = set()
            for entry in found:
                key = entry["mac"] or f"ip:{entry['ip']}"
                seen.add(key)
                d = self.devices.get(key)
                is_new = d is None
                if is_new:
                    d = {"key": key, "first_seen": now, "sessions": [], "ports": [], "studied": 0, "name": "",
                         "room": "", "owner": "", "trusted": False, "notes": ""}
                    self.devices[key] = d
                d.update({k: v for k, v in entry.items() if v})
                sessions = d.setdefault("sessions", [])
                if sessions and now - sessions[-1][1] <= SCAN_EVERY * 2.5:
                    sessions[-1][1] = now
                else:
                    sessions.append([now, now])
                    del sessions[:-MAX_SESSIONS]
                d["last_seen"], d["online"] = now, True
                d["type"] = self.classify(d)
                if is_new:
                    store.event("INFO", f"Nuovo dispositivo in rete: {self.label(d)} ({d['ip']})", "network")
                    if self.on_new_device and self.last_scan:
                        await self.on_new_device(d)
                if now - d.get("studied", 0) > RESTUDY_EVERY and self.queue:
                    self.queue.put_nowait(key)
            for key, d in self.devices.items():
                if key not in seen:
                    d["online"] = False
            self.last_scan = now
            self.save()
            return {"status": "ok", "found": len(found), "total": len(self.devices)}
        finally:
            self.scanning = False

    async def study(self, key: str) -> dict:
        d = self.devices.get(key)
        if not d or not d.get("ip") or DEMO:
            return d or {}
        code, xml = await sh("nmap", "-sV", "-O", "--osscan-limit", "--top-ports", "200", "-T4", "--version-light",
                             "-oX", "-", d["ip"], timeout=600)
        ports, os_name = [], ""
        if code == 0 and xml:
            host = ET.fromstring(xml).find("host")
            if host is not None:
                for p in host.findall("ports/port"):
                    if p.find("state").get("state") != "open":
                        continue
                    svc = p.find("service")
                    ports.append({"port": int(p.get("portid")), "proto": p.get("protocol"),
                                  "service": svc.get("name", "") if svc is not None else "",
                                  "product": " ".join(x for x in ((svc.get("product") if svc is not None else ""),
                                                                  (svc.get("version") if svc is not None else "")) if x)})
                match = host.find("os/osmatch")
                if match is not None:
                    os_name = f"{match.get('name')} ({match.get('accuracy')}%)"
        d["ports"], d["os"] = ports, os_name or d.get("os", "")
        for p in ports:
            if p["port"] in (80, 8080, 443, 8443, 8123, 5000) and not d.get("web_title"):
                scheme = "https" if p["port"] in (443, 8443, 5001) else "http"
                try:
                    async with httpx.AsyncClient(timeout=5, verify=False, follow_redirects=True) as client:
                        r = await client.get(f"{scheme}://{d['ip']}:{p['port']}/")
                    m = re.search(r"<title[^>]*>([^<]{1,120})", r.text, re.I)
                    if m:
                        d["web_title"] = m.group(1).strip()
                except httpx.HTTPError:
                    pass
        d["studied"] = time.time()
        d["type"] = self.classify(d)
        self.save()
        store.event("INFO", f"Dispositivo studiato: {self.label(d)} — {len(ports)} servizi", "network")
        if self.on_device_learned:
            await self.on_device_learned(d)
        return d

    def label(self, d: dict) -> str:
        return (d.get("name") or d.get("hostname") or d.get("web_title") or
                (f"{d['vendor']} {TYPES.get(d.get('type'), TYPES['unknown'])[0]}" if d.get("vendor")
                 else TYPES.get(d.get("type"), TYPES["unknown"])[0]))

    def habits(self, d: dict) -> str:
        sessions = d.get("sessions") or []
        if len(sessions) < 3:
            return "Dati insufficienti"
        hours = Counter(time.localtime(s[0]).tm_hour for s in sessions)
        top = sorted(h for h, _ in hours.most_common(2))
        always = sum(s[1] - s[0] for s in sessions) / max(1, sessions[-1][1] - sessions[0][0]) > 0.9
        return "Sempre connesso" if always else "Si connette di solito verso le " + " e le ".join(f"{h}:00" for h in top)

    def listing(self) -> dict:
        items = []
        for d in self.devices.values():
            t = TYPES.get(d.get("type"), TYPES["unknown"])
            items.append({**{k: v for k, v in d.items() if k != "sessions"}, "label": self.label(d),
                          "type_label": t[0], "icon": t[1], "habits": self.habits(d)})
        items.sort(key=lambda x: (not x.get("online"), [int(p) for p in (x.get("ip") or "0.0.0.0").split(".")]))
        return {"subnet": self.subnet, "gateway": self.gateway, "last_scan": self.last_scan,
                "scanning": self.scanning, "devices": items, "types": {k: v[0] for k, v in TYPES.items()}}

    def update(self, key: str, changes: dict) -> dict:
        d = self.devices.get(key)
        if not d:
            raise KeyError(key)
        for k in ("name", "room", "owner", "notes"):
            if k in changes:
                d[k] = str(changes[k])[:200]
        if "trusted" in changes:
            d["trusted"] = bool(changes["trusted"])
        if changes.get("type") in TYPES:
            d["type"], d["type_manual"] = changes["type"], True
        self.save()
        return d

    def summary_text(self) -> str:
        online = [d for d in self.devices.values() if d.get("online")]
        kinds = Counter(TYPES.get(d.get("type"), TYPES["unknown"])[0].lower() for d in online)
        parts = ", ".join(f"{n} {k}" for k, n in kinds.most_common(5))
        return f"In rete ci sono {len(online)} dispositivi connessi" + (f": {parts}." if parts else ".")

    async def run(self) -> None:
        self.queue = asyncio.Queue()
        asyncio.create_task(self._study_worker())
        await asyncio.sleep(60)
        while True:
            if env_get("JARVIS_NETWORK", "1") == "0":
                await asyncio.sleep(30)
                continue
            try:
                await self.scan()
            except Exception as exc:
                log.warning("Scansione di rete non riuscita: %s", exc)
            await asyncio.sleep(SCAN_EVERY)

    async def _study_worker(self) -> None:
        while True:
            key = await self.queue.get()
            try:
                await self.study(key)
            except Exception as exc:
                log.warning("Studio del dispositivo %s non riuscito: %s", key, exc)
            await asyncio.sleep(5)


explorer = NetworkExplorer()
