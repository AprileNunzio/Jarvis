from fastapi import APIRouter, Depends, HTTPException, Request

from access import require_admin
from core_client import core
from features.desktop.desk import desk
from features.network.explorer import explorer
from features.telegram.bot import bot, esc
from state import store
from tasks import background

admin_routes = APIRouter()


async def _new_device(d: dict) -> None:
    desk.show("notice", {"icon": d.get("icon", "📡"), "title": "Nuovo dispositivo in rete",
                         "text": f"{explorer.label(d)} · {d.get('ip', '')}"}, key=f"net:{d.get('key', '')}")
    await bot.notify(f"📡 <b>Nuovo dispositivo in rete</b>\n{esc(explorer.label(d))}\n"
                     f"IP {esc(d.get('ip'))} · MAC {esc(d.get('mac'))} · "
                     f"{esc(d.get('vendor') or 'produttore sconosciuto')}")


async def _learned(d: dict) -> None:
    props = {"ip": d.get("ip"), "mac": d.get("mac"), "vendor": d.get("vendor"), "type": d.get("type"),
             "os": d.get("os"), "services": [f"{p['port']}/{p['service']}" for p in d.get("ports", [])][:20]}
    await core.remember(("node", {"id": f"device:{d['key']}", "node_type": "DEVICE",
                                  "label": explorer.label(d), "properties": props}))


explorer.on_new_device = _new_device
explorer.on_device_learned = _learned


@admin_routes.get("/api/network")
async def admin_network(_: str = Depends(require_admin)):
    return explorer.listing()


@admin_routes.post("/api/network/scan")
async def admin_network_scan(user: str = Depends(require_admin)):
    store.event("INFO", f"Scansione di rete richiesta da {user}", "network")
    background(explorer.scan())
    return {"ok": True}


@admin_routes.post("/api/network/study/{key:path}")
async def admin_network_study(key: str, _: str = Depends(require_admin)):
    if key not in explorer.devices:
        raise HTTPException(404, "Dispositivo sconosciuto")
    background(explorer.study(key))
    return {"ok": True}


@admin_routes.put("/api/network/devices/{key:path}")
async def admin_network_update(key: str, request: Request, _: str = Depends(require_admin)):
    try:
        d = explorer.update(key, await request.json())
    except KeyError:
        raise HTTPException(404, "Dispositivo sconosciuto")
    background(_learned(d))
    return {"ok": True}
