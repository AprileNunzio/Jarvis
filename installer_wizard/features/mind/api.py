from fastapi import APIRouter, Depends, HTTPException, Request

from access import require_admin

from features.mind.mind import mind

admin_routes = APIRouter()


@admin_routes.get("/api/mind")
async def admin_mind(_: str = Depends(require_admin)):
    return mind.summary()


@admin_routes.put("/api/mind")
async def admin_mind_settings(request: Request, _: str = Depends(require_admin)):
    changes = await request.json()
    return {"settings": mind.update_settings(changes if isinstance(changes, dict) else {})}


@admin_routes.delete("/api/mind/facts/{fid}")
async def admin_mind_forget(fid: str, _: str = Depends(require_admin)):
    if not mind.memory.forget(fid):
        raise HTTPException(404, "Ricordo sconosciuto")
    mind.publish()
    return {"ok": True}


@admin_routes.delete("/api/mind/suggestions/{sid}")
async def admin_mind_dismiss(sid: str, _: str = Depends(require_admin)):
    if not mind.dismiss(sid):
        raise HTTPException(404, "Suggerimento sconosciuto")
    return {"ok": True}


@admin_routes.post("/api/mind/clear")
async def admin_mind_clear(_: str = Depends(require_admin)):
    n = mind.memory.clear()
    mind.publish()
    return {"ok": True, "removed": n}


