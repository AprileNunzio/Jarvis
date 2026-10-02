from access import require_admin
from fastapi import APIRouter, Depends, HTTPException, Request
from state import store
from tasks import background

from features.bluetooth import adapter, prefs
from features.bluetooth.service import service

admin_routes = APIRouter()
ACTIONS = {"pair": adapter.pair, "connect": adapter.connect, "disconnect": adapter.disconnect,
           "forget": adapter.forget}


def _view(state: dict) -> dict:
    data = prefs.load()
    devices = [{**d, "settings": prefs.device(data, d["mac"])} for d in state["devices"]]
    return {**state, "devices": devices, "prefs": {k: data[k] for k in ("output_order", "input_order", *prefs.GLOBALS)},
            "roles": prefs.ROLES, "profiles": prefs.PROFILES, "enabled": service.enabled()}


@admin_routes.get("/api/bluetooth")
async def bluetooth_state(_: str = Depends(require_admin)):
    return _view(await service.refresh())


@admin_routes.post("/api/bluetooth/scan")
async def bluetooth_scan(_: str = Depends(require_admin)):
    if not service.state["controller"].get("installed"):
        raise HTTPException(409, "Nessun adattatore Bluetooth pronto")
    background(service.scan(20))
    return {"ok": True, "seconds": 20}


@admin_routes.post("/api/bluetooth/devices/{mac}/{action}")
async def bluetooth_action(mac: str, action: str, user: str = Depends(require_admin)):
    if action not in ACTIONS:
        raise HTTPException(404, "Azione sconosciuta")
    try:
        mac = adapter.valid_mac(mac)
        await ACTIONS[action](mac)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except adapter.BluetoothError as exc:
        raise HTTPException(502, f"Il dispositivo non ha risposto: {exc}")
    state = await service.refresh()
    dev = next((d for d in state["devices"] if d["mac"] == mac), None)
    if action == "forget":
        prefs.forget(mac)
    elif dev and action in ("pair", "connect"):
        prefs.remember(mac, dev["name"], dev["audio_out"], dev["audio_in"])
    store.event("INFO", f"Bluetooth {action} {dev['name'] if dev else mac} da {user}", "bluetooth")
    return _view(await service.refresh())


@admin_routes.put("/api/bluetooth/prefs")
async def bluetooth_prefs(request: Request, _: str = Depends(require_admin)):
    try:
        prefs.update(await request.json())
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return _view(await service.refresh())
