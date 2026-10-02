import asyncio
import re
import shutil
from pathlib import Path

from config import DEMO

MAC_RE = re.compile(r"^[0-9A-F]{2}(:[0-9A-F]{2}){5}$")
SYS_BT = Path("/sys/class/bluetooth")
AUDIO_SINK = {"0000110b", "0000110d"}
AUDIO_SOURCE = {"0000110a"}
HEADSET = {"00001108", "00001112", "0000111e", "0000111f", "00001131"}
KINDS = {"audio-headset": "Auricolari", "audio-headphones": "Cuffie", "audio-card": "Cassa",
         "input-microphone": "Microfono", "phone": "Telefono", "computer": "Computer", "input-keyboard": "Tastiera",
         "input-mouse": "Mouse", "input-gaming": "Controller"}
_DEMO = [
    {"mac": "11:22:33:44:55:66", "name": "Cuffie Sony WH-1000XM5", "icon": "audio-headphones", "paired": True,
     "trusted": True, "connected": True, "battery": 80, "uuids": ["0000110b", "0000111e"]},
    {"mac": "AA:BB:CC:DD:EE:01", "name": "JBL Flip 6", "icon": "audio-card", "paired": True, "trusted": True,
     "connected": False, "battery": None, "uuids": ["0000110b"]},
]


class BluetoothError(RuntimeError):
    pass


def valid_mac(mac: str) -> str:
    mac = str(mac or "").strip().upper()
    if not MAC_RE.match(mac):
        raise ValueError("Indirizzo del dispositivo non valido")
    return mac


def has_adapter() -> bool:
    return DEMO or any(SYS_BT.glob("hci*"))


def installed() -> bool:
    return DEMO or shutil.which("bluetoothctl") is not None


async def ctl(*args: str, timeout: float = 15) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec("bluetoothctl", *args, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.STDOUT)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, "tempo scaduto"
    return proc.returncode or 0, re.sub(r"\x1b\[[0-9;]*m", "", out.decode("utf-8", "replace"))


def _parse_info(mac: str, text: str) -> dict:
    field = lambda name: (re.search(rf"^\s*{name}:\s*(.+)$", text, re.M) or [None, ""])[1].strip()
    battery = re.search(r"Battery Percentage:.*\((\d+)\)", text)
    return {
        "mac": mac,
        "name": field("Alias") or field("Name") or mac,
        "icon": field("Icon"),
        "paired": field("Paired") == "yes",
        "trusted": field("Trusted") == "yes",
        "connected": field("Connected") == "yes",
        "battery": int(battery.group(1)) if battery else None,
        "uuids": sorted({u[:8].lower() for u in re.findall(r"UUID:.*\(([0-9a-fA-F-]{36})\)", text)}),
    }


def describe(dev: dict) -> dict:
    uuids = set(dev.get("uuids") or [])
    icon = dev.get("icon") or ""
    output = bool(uuids & AUDIO_SINK) or icon in ("audio-headset", "audio-headphones", "audio-card")
    mic = bool(uuids & HEADSET) or icon in ("audio-headset", "input-microphone")
    return {**dev, "kind": KINDS.get(icon, "Dispositivo"), "audio_out": output, "audio_in": mic or bool(uuids & AUDIO_SOURCE)}


async def controller() -> dict:
    if DEMO:
        return {"present": True, "installed": True, "powered": True, "discovering": False, "name": "Demo", "address": ""}
    if not has_adapter():
        return {"present": False, "installed": installed(), "powered": False, "discovering": False}
    if not installed():
        return {"present": True, "installed": False, "powered": False, "discovering": False}
    _, out = await ctl("show")
    field = lambda name: (re.search(rf"^\s*{name}:\s*(.+)$", out, re.M) or [None, ""])[1].strip()
    address = re.search(r"Controller ([0-9A-F:]{17})", out)
    return {"present": True, "installed": True, "powered": field("Powered") == "yes",
            "discovering": field("Discovering") == "yes", "name": field("Alias") or field("Name"),
            "address": address.group(1) if address else ""}


async def devices() -> list[dict]:
    if DEMO:
        return [describe(d) for d in _DEMO]
    _, out = await ctl("devices")
    macs = [m for m in re.findall(r"^Device ([0-9A-F:]{17})", out, re.M)]
    infos = await asyncio.gather(*(ctl("info", mac) for mac in macs))
    return [describe(_parse_info(mac, text)) for mac, (_, text) in zip(macs, infos)]


async def _run(*args: str, timeout: float = 30, ok: str = "") -> str:
    code, out = await ctl(*args, timeout=timeout)
    if code != 0 or (ok and ok not in out):
        tail = out.strip().splitlines()[-1] if out.strip() else f"codice {code}"
        raise BluetoothError(tail[:200])
    return out


async def power(on: bool) -> None:
    if not DEMO:
        await _run("power", "on" if on else "off")


async def scan(seconds: int) -> None:
    if not DEMO:
        await ctl("--timeout", str(max(5, min(60, seconds))), "scan", "on", timeout=seconds + 10)


async def pair(mac: str) -> None:
    mac = valid_mac(mac)
    if DEMO:
        return
    await _run("--agent=NoInputNoOutput", "pair", mac, timeout=45)
    await _run("trust", mac)


async def connect(mac: str) -> None:
    mac = valid_mac(mac)
    if not DEMO:
        await _run("connect", mac, timeout=30, ok="Connection successful")


async def disconnect(mac: str) -> None:
    mac = valid_mac(mac)
    if not DEMO:
        await _run("disconnect", mac)


async def forget(mac: str) -> None:
    mac = valid_mac(mac)
    if not DEMO:
        await _run("remove", mac)
