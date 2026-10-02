import asyncio
import hashlib
import json
import logging
import re

from config import DEMO

log = logging.getLogger("jarvis.audio")

KIOSK_USER = "jarvis-kiosk"
WATCH_SECONDS = 3
_demo = {"output": {"volume": 70, "muted": False, "device": "demo.speakers"},
         "input": {"volume": 80, "muted": False, "device": "demo.mic"}}
_DEMO_DEVICES = {
    "outputs": [{"name": "demo.speakers", "label": "Altoparlanti integrati", "kind": "sink"},
                {"name": "demo.speakers#analog-output-headphones", "label": "Cuffie", "kind": "port"},
                {"name": "profile:demo:output:hdmi-stereo", "label": "HDMI — Uscita digitale (attiva il profilo)",
                 "kind": "profile"}],
    "inputs": [{"name": "demo.mic", "label": "Microfono interno", "kind": "source"}],
}


async def _pactl(*args: str) -> tuple[int, str]:
    import pwd
    try:
        uid = pwd.getpwnam(KIOSK_USER).pw_uid
    except KeyError:
        return 1, "utente kiosk assente"
    proc = await asyncio.create_subprocess_exec(
        "runuser", "-u", KIOSK_USER, "--", "env", f"XDG_RUNTIME_DIR=/run/user/{uid}", "LC_ALL=C", "LANG=C",
        "pactl", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), 8)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, "timeout"
    text = out.decode("utf-8", "replace")
    if proc.returncode:
        text = (err.decode("utf-8", "replace") or text).strip()
    return proc.returncode or 0, text


async def pactl(*args: str) -> tuple[int, str]:
    return await _pactl(*args)


async def pactl_json(kind: str) -> list:
    code, out = await _pactl("-f", "json", "list", kind)
    return json.loads(out) if code == 0 and out.strip().startswith("[") else []


def _percent(text: str) -> int:
    m = re.search(r"(\d+)%", text)
    return int(m.group(1)) if m else 0


def _parse_text(out: str) -> list[dict]:
    items, cur, section, sub = [], None, None, None
    for raw in out.splitlines():
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip("\t"))
        line = raw.strip()
        if indent == 0:
            cur = {"ports": [], "profiles": {}}
            items.append(cur)
            section = None
            continue
        if cur is None:
            continue
        if indent == 1:
            section, sub = None, None
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip()
            if key in ("Ports", "Profiles", "Properties") and not value:
                section = key
            elif key == "Name":
                cur["name"] = value
            elif key == "Description":
                cur["description"] = value
            elif key == "Active Port":
                cur["active_port"] = value
            elif key == "Active Profile":
                cur["active_profile"] = value
            elif key == "Monitor of Sink" and value != "n/a":
                cur["monitor_of"] = value
        elif indent == 2 and section == "Ports":
            m = re.match(r"(\S+): (.*) \(([^()]*)\)$", line)
            if m:
                sub = {"name": m.group(1), "description": m.group(2),
                       "availability": "no" if "not available" in m.group(3) else "yes"}
                cur["ports"].append(sub)
        elif indent == 2 and section == "Profiles":
            m = re.match(r"(\S+): (.*) \(([^()]*)\)$", line)
            if m:
                props = dict(re.findall(r"(\w+): ([^,]+)", m.group(3)))
                cur["profiles"][m.group(1)] = {"description": m.group(2),
                                               "sinks": int(props.get("sinks", 0) or 0),
                                               "sources": int(props.get("sources", 0) or 0),
                                               "available": props.get("available", "yes").strip() != "no"}
        elif indent == 2 and section == "Properties":
            key, _, value = line.partition(" = ")
            cur.setdefault("properties", {})[key.strip()] = value.strip().strip('"')
    return [i for i in items if i.get("name")]


def _normalize_json(items: list) -> list[dict]:
    out = []
    for d in items:
        raw_ports = d.get("ports") if isinstance(d.get("ports"), list) else []
        ports = [{"name": p.get("name"), "description": p.get("description") or p.get("name"),
                  "availability": "no" if p.get("availability") == "not available" else "yes"}
                 for p in raw_ports if isinstance(p, dict)]
        profiles = {}
        for name, p in (d.get("profiles") or {}).items():
            profiles[name] = {"description": p.get("description") or name, "sinks": int(p.get("sinks", 0) or 0),
                              "sources": int(p.get("sources", 0) or 0), "available": p.get("available", True) is not False}
        monitor = d.get("monitor_of_sink")
        out.append({"name": d.get("name"), "description": d.get("description") or d.get("name"),
                    "active_port": d.get("active_port"), "active_profile": d.get("active_profile"),
                    "monitor_of": monitor if monitor and monitor != "n/a" else None,
                    "properties": d.get("properties") or {}, "ports": ports, "profiles": profiles})
    return out


async def _list(kind: str) -> list[dict]:
    code, out = await _pactl("-f", "json", "list", kind)
    if code == 0:
        try:
            return _normalize_json(json.loads(out))
        except ValueError:
            pass
    code, out = await _pactl("list", kind)
    return _parse_text(out) if code == 0 else []


def _port_ok(p: dict) -> bool:
    return p.get("availability") not in ("no", "not available")


async def devices() -> dict:
    if DEMO:
        return {k: list(v) for k, v in _DEMO_DEVICES.items()}
    sinks, sources, cards = await asyncio.gather(_list("sinks"), _list("sources"), _list("cards"))

    def expand(items: list, kind: str) -> list:
        entries = []
        for d in items:
            if kind == "source" and (d["name"].endswith(".monitor") or d.get("monitor_of")):
                continue
            label = d.get("description") or d["name"]
            ports = [p for p in d.get("ports", []) if _port_ok(p)]
            if len(ports) > 1:
                for p in ports:
                    entries.append({"name": f"{d['name']}#{p['name']}", "label": f"{label} — {p['description']}",
                                    "kind": "port", "device": d["name"], "port": p["name"],
                                    "active": p["name"] == d.get("active_port")})
            else:
                entries.append({"name": d["name"], "label": label, "kind": kind, "device": d["name"]})
        return entries

    outputs, inputs = expand(sinks, "sink"), expand(sources, "source")
    for card in cards:
        active = card.get("active_profile") or ""
        parts = dict(x.split(":", 1) for x in active.split("+") if ":" in x)
        card_label = card.get("properties", {}).get("device.description") or card.get("description") or card["name"]
        profiles = {n: p for n, p in card.get("profiles", {}).items() if n != active and n != "off" and p["available"]}

        def keeps(name: str, side: str) -> bool:
            other = parts.get(side)
            if not other:
                return True
            with_other = [n for n in profiles if f"{side}:{other}" in n.split("+")]
            return not with_other or f"{side}:{other}" in name.split("+")

        for pname, p in profiles.items():
            mine = dict(x.split(":", 1) for x in pname.split("+") if ":" in x)
            entry = {"name": f"profile:{card['name']}:{pname}", "kind": "profile", "card": card["name"],
                     "profile": pname, "label": f"{card_label} — {p['description']} (attiva il profilo)"}
            if p["sinks"] and mine.get("output") != parts.get("output") and keeps(pname, "input"):
                outputs.append(entry)
            elif p["sources"] and mine.get("input") != parts.get("input") and keeps(pname, "output"):
                inputs.append(entry)
    return {"outputs": outputs, "inputs": inputs}


def signature(devs: dict) -> str:
    return hashlib.sha1(json.dumps(devs, sort_keys=True).encode()).hexdigest()[:12]


async def status() -> dict:
    if DEMO:
        return {**_demo, "available": True, **await devices()}
    code, vol = await _pactl("get-sink-volume", "@DEFAULT_SINK@")
    if code != 0:
        return {"available": False, "error": vol.strip()[:200], "outputs": [], "inputs": []}
    (_, mute), (_, svol), (_, smute), (_, sink), (_, source), devs = await asyncio.gather(
        _pactl("get-sink-mute", "@DEFAULT_SINK@"), _pactl("get-source-volume", "@DEFAULT_SOURCE@"),
        _pactl("get-source-mute", "@DEFAULT_SOURCE@"), _pactl("get-default-sink"), _pactl("get-default-source"),
        devices())
    sink, source = sink.strip(), source.strip()

    def current(entries: list, default: str) -> str:
        for e in entries:
            if e.get("device") == default and e.get("kind") == "port" and e.get("active"):
                return e["name"]
        return default

    return {
        "available": True,
        "output": {"volume": _percent(vol), "muted": "yes" in mute.lower(), "device": current(devs["outputs"], sink)},
        "input": {"volume": _percent(svol), "muted": "yes" in smute.lower(), "device": current(devs["inputs"], source)},
        "outputs": devs["outputs"], "inputs": devs["inputs"], "signature": signature(devs),
    }


async def _select(kind: str, value: str) -> None:
    target = "sink" if kind == "output" else "source"
    if value.startswith("profile:"):
        _, card, profile = value.split(":", 2)
        await _pactl("set-card-profile", card, profile)
        await asyncio.sleep(0.6)
        devs = await devices()
        fresh = [e for e in devs["outputs" if kind == "output" else "inputs"]
                 if e.get("kind") != "profile" and card.split(".", 1)[-1] in e.get("device", "")]
        if fresh:
            await _select(kind, fresh[0]["name"])
        return
    device, _, port = value.partition("#")
    await _pactl(f"set-default-{target}", device)
    if port:
        await _pactl(f"set-{target}-port", device, port)


async def update(changes: dict) -> dict:
    for kind, target in (("output", "sink"), ("input", "source")):
        c = changes.get(kind) or {}
        if DEMO:
            _demo[kind].update({k: v for k, v in c.items() if k in ("volume", "muted", "device")})
            continue
        if c.get("device"):
            await _select(kind, str(c["device"]))
        if "volume" in c:
            vol = max(0, min(150, int(c["volume"])))
            await _pactl(f"set-{target}-volume", f"@DEFAULT_{target.upper()}@", f"{vol}%")
        if "muted" in c:
            await _pactl(f"set-{target}-mute", f"@DEFAULT_{target.upper()}@", "1" if c["muted"] else "0")
    return await status()


class DeviceWatcher:

    def __init__(self) -> None:
        self.signature = ""
        self.names: dict = {}
        self.on_change = None

    async def run(self) -> None:
        from state import store
        while True:
            try:
                devs = await devices()
                sig = signature(devs)
                if sig != self.signature:
                    names = {e["name"]: e["label"] for e in devs["outputs"] + devs["inputs"] if e["kind"] != "profile"}
                    if self.signature:
                        added = [names[n] for n in names if n not in self.names]
                        removed = [self.names[n] for n in self.names if n not in names]
                        for label in added:
                            store.event("INFO", f"Dispositivo audio collegato: {label}", "audio")
                        for label in removed:
                            store.event("INFO", f"Dispositivo audio scollegato: {label}", "audio")
                    self.signature, self.names = sig, names
                    store.audio_rev = sig
                    store.touch()
            except Exception as exc:
                log.debug("Controllo dispositivi audio non riuscito: %s", exc)
            await asyncio.sleep(WATCH_SECONDS)


watcher = DeviceWatcher()
