from config import DEMO

from features.bluetooth import prefs
from features.devices import audio


def _key(mac: str) -> str:
    return mac.replace(":", "_")


def _role(dev: dict, settings: dict) -> str:
    if settings["role"] != "auto":
        return settings["role"]
    if dev["audio_out"] and dev["audio_in"]:
        return "both"
    return "output" if dev["audio_out"] else "input" if dev["audio_in"] else "off"


def choose(devs: list[dict], data: dict) -> dict:
    live = {d["mac"]: d for d in devs if d["connected"]}
    roles = {mac: _role(d, prefs.device(data, mac)) for mac, d in live.items()}
    output = next((m for m in data["output_order"] if m in live and roles[m] in ("output", "both")), None)
    inputs = [m for m in data["input_order"] if m in live and roles[m] in ("input", "both")]
    microphone = next((m for m in inputs if prefs.device(data, m)["profile"] != "quality"), None)
    return {"output": output, "input": microphone, "roles": roles}


def _pick(profiles: dict, wanted: str) -> str | None:
    names = [n for n, p in profiles.items() if p.get("available", True) and n != "off"]
    if wanted == "headset":
        return next((n for n in names if "handsfree_head_unit" in n), None) or next(
            (n for n in names if "head_unit" in n or "headset" in n), None)
    return next((n for n in names if "a2dp" in n and "sink" in n), None) or next((n for n in names if "a2dp" in n), None)


async def _profiles(choice: dict, data: dict) -> None:
    cards = {c["name"]: c for c in await audio.pactl_json("cards") if c.get("name", "").startswith("bluez_card.")}
    for mac, role in choice["roles"].items():
        card = cards.get(f"bluez_card.{_key(mac)}")
        if not card or role == "off":
            continue
        profile = prefs.device(data, mac)["profile"]
        wants_mic = profile == "headset" or (profile == "auto" and mac == choice["input"])
        target = _pick(card.get("profiles") or {}, "headset" if wants_mic else "quality")
        if target and target != card.get("active_profile"):
            await audio.pactl("set-card-profile", card["name"], target)


async def _node(kind: str, mac: str) -> str | None:
    items = await audio.pactl_json("sinks" if kind == "sink" else "sources")
    for item in items:
        name = item.get("name", "")
        if _key(mac) in name and not name.endswith(".monitor"):
            return name
    return None


class Router:
    def __init__(self) -> None:
        self.fallback = {"sink": "", "source": ""}
        self.active = {"sink": "", "source": ""}

    async def _default(self, kind: str) -> str:
        _, out = await audio.pactl(f"get-default-{kind}")
        return out.strip()

    async def _switch(self, kind: str, mac: str | None) -> bool:
        current = await self._default(kind)
        if mac:
            node = await _node(kind, mac)
            if not node or node == current:
                return False
            if not current.startswith("bluez_"):
                self.fallback[kind] = current
            await audio.pactl(f"set-default-{kind}", node)
            self.active[kind] = node
            return True
        if current.startswith("bluez_") and self.fallback[kind]:
            await audio.pactl(f"set-default-{kind}", self.fallback[kind])
            self.active[kind] = ""
            return True
        return False

    async def apply(self, devs: list[dict]) -> dict:
        data = prefs.load()
        choice = choose(devs, data)
        if DEMO:
            return {**choice, "changed": False}
        await _profiles(choice, data)
        changed = False
        if data["auto_switch"]:
            changed = await self._switch("sink", choice["output"]) | await self._switch("source", choice["input"])
        return {**choice, "changed": changed}


router = Router()
