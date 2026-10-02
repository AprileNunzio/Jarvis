from fastapi import APIRouter, Depends, HTTPException, Request

from access import require_admin
from feature_registry import registry
from orchestrator import converge_steps
from settings import apply_config
from state import store
from tasks import background

admin_routes = APIRouter()
registry.converge = converge_steps


@admin_routes.get("/api/features")
async def admin_features(_: str = Depends(require_admin)):
    registry.scan()
    return registry.listing()


@admin_routes.post("/api/features/rescan")
async def admin_features_rescan(_: str = Depends(require_admin)):
    registry.signature = ""
    await registry.probe_hardware()
    registry.scan()
    background(registry.sync())
    return registry.listing()


@admin_routes.put("/api/features/{fid}")
async def admin_feature_update(fid: str, request: Request, user: str = Depends(require_admin)):
    body = await request.json()
    try:
        if "mode" in body:
            registry.set_mode(fid, str(body["mode"]))
            store.event("INFO", f"Funzionalità «{registry.features[fid]['name']}»: modalità {body['mode']} ({user})",
                        "features")
        if "pinned" in body:
            registry.set_pinned(fid, bool(body["pinned"]))
    except KeyError:
        raise HTTPException(404, "Funzionalità sconosciuta")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    background(registry.sync())
    return registry.listing()


@admin_routes.put("/api/features/{fid}/settings")
async def admin_feature_settings(fid: str, request: Request, user: str = Depends(require_admin)):
    if fid not in registry.features:
        raise HTTPException(404, "Funzionalità sconosciuta")
    try:
        env_updates, steps = registry.save_settings(fid, await request.json())
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    applying = await apply_config(env_updates, user, steps) if env_updates else []
    return {"ok": True, "applying": applying, "values": registry.settings_of(fid)}
