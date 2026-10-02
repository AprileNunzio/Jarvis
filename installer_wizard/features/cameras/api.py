from fastapi import APIRouter, Depends, HTTPException, Request

from access import require_admin

from features.cameras.cameras import cameras

admin_routes = APIRouter()


@admin_routes.get("/api/cameras")
async def admin_cameras(_: str = Depends(require_admin)):
    return cameras.listing()


@admin_routes.post("/api/cameras")
async def admin_cameras_add(request: Request, _: str = Depends(require_admin)):
    try:
        return cameras._safe(cameras.add(await request.json()))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@admin_routes.put("/api/cameras/{cid}")
async def admin_cameras_update(cid: str, request: Request, _: str = Depends(require_admin)):
    try:
        return cameras._safe(cameras.update(cid, await request.json()))
    except KeyError:
        raise HTTPException(404, "Telecamera sconosciuta")
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@admin_routes.delete("/api/cameras/{cid}")
async def admin_cameras_delete(cid: str, _: str = Depends(require_admin)):
    try:
        cameras.delete(cid)
    except KeyError:
        raise HTTPException(404, "Telecamera sconosciuta")
    return {"ok": True}
