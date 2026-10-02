from fastapi import APIRouter, Depends, HTTPException, Request

from access import require_admin

from features.laws.laws import laws

admin_routes = APIRouter()


@admin_routes.get("/api/laws")
async def admin_laws(_: str = Depends(require_admin)):
    return laws.listing()


@admin_routes.post("/api/laws")
async def admin_laws_add(request: Request, _: str = Depends(require_admin)):
    text = str((await request.json()).get("text", ""))
    try:
        return laws.add(text)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@admin_routes.put("/api/laws/{rid}")
async def admin_laws_update(rid: str, request: Request, _: str = Depends(require_admin)):
    text = str((await request.json()).get("text", ""))
    try:
        return laws.update(rid, text)
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    except KeyError:
        raise HTTPException(404, "Regola sconosciuta")
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@admin_routes.delete("/api/laws/{rid}")
async def admin_laws_delete(rid: str, _: str = Depends(require_admin)):
    try:
        laws.delete(rid)
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    except KeyError:
        raise HTTPException(404, "Regola sconosciuta")
    return {"ok": True}


@admin_routes.post("/api/laws/reorder")
async def admin_laws_reorder(request: Request, _: str = Depends(require_admin)):
    order = (await request.json()).get("order") or []
    laws.reorder([str(x) for x in order])
    return {"ok": True}
