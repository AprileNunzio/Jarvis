import json
import os

from config import STATE_DIR

from features.bluetooth.adapter import valid_mac

PREFS_FILE = STATE_DIR / "bluetooth.json"
ROLES = {"auto": "Automatico", "output": "Solo uscita (ascolto)", "input": "Solo ingresso (microfono)",
         "both": "Uscita e microfono", "off": "Non usare per l'audio"}
PROFILES = {"auto": "Automatico: microfono solo quando serve", "quality": "Alta qualità (A2DP, senza microfono)",
            "headset": "Auricolare con microfono (HFP)"}
GLOBALS = {"auto_switch": True, "auto_connect": True, "announce": True}


def _default() -> dict:
    return {"devices": {}, "output_order": [], "input_order": [], **GLOBALS}


def load() -> dict:
    if not PREFS_FILE.exists():
        return _default()
    return {**_default(), **json.loads(PREFS_FILE.read_text(encoding="utf-8"))}


def save(data: dict) -> None:
    tmp = PREFS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, PREFS_FILE)


def device(data: dict, mac: str) -> dict:
    return {"role": "auto", "profile": "auto", "autoconnect": True, **data["devices"].get(mac, {})}


def remember(mac: str, name: str, audio_out: bool, audio_in: bool) -> dict:
    data = load()
    entry = data["devices"].setdefault(mac, {})
    entry["name"] = str(name)[:80]
    if audio_out and mac not in data["output_order"]:
        data["output_order"].append(mac)
    if audio_in and mac not in data["input_order"]:
        data["input_order"].append(mac)
    save(data)
    return data


def forget(mac: str) -> None:
    data = load()
    data["devices"].pop(mac, None)
    data["output_order"] = [m for m in data["output_order"] if m != mac]
    data["input_order"] = [m for m in data["input_order"] if m != mac]
    save(data)


def update(changes: dict) -> dict:
    data = load()
    for key in ("output_order", "input_order"):
        if key in changes:
            macs = [valid_mac(m) for m in changes[key] or []]
            if len(macs) > 32:
                raise ValueError("Troppi dispositivi nella lista")
            data[key] = list(dict.fromkeys(macs))
    for key in GLOBALS:
        if key in changes:
            data[key] = bool(changes[key])
    for mac, settings in (changes.get("devices") or {}).items():
        mac = valid_mac(mac)
        entry = data["devices"].setdefault(mac, {})
        if settings.get("role") in ROLES:
            entry["role"] = settings["role"]
        if settings.get("profile") in PROFILES:
            entry["profile"] = settings["profile"]
        if "autoconnect" in settings:
            entry["autoconnect"] = bool(settings["autoconnect"])
    save(data)
    return data
