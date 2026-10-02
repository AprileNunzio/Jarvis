from config import VERSION
from pages import ASSET_VERSION
from state import store


def master() -> dict:
    sysinfo = store.system or {}
    comps = store.components or {}
    down = [c["label"] for c in comps.values() if c.get("status") not in ("ok", "idle")]
    update = store.update or {}
    return {
        "name": sysinfo.get("hostname") or "Server Jarvis",
        "ip": sysinfo.get("ip", ""),
        "phase": store.phase,
        "version": VERSION,
        "revision": ASSET_VERSION,
        "update_available": bool(update.get("available")),
        "uptime": sysinfo.get("uptime", 0),
        "metrics": {"cpu": sysinfo.get("cpu_percent"), "ram": sysinfo.get("mem_percent"),
                    "disk": sysinfo.get("disk_percent"), "temp": sysinfo.get("temperature")},
        "components": [{"label": c["label"], "status": c.get("status", "idle"), "detail": c.get("detail", "")}
                       for c in comps.values()],
        "problems": down,
    }
