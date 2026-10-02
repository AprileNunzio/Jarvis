import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from access import is_local, require_admin
from features.location import locator as location
from state import store

public_routes = APIRouter()
admin_routes = APIRouter()


@public_routes.post("/api/location/browser")
async def public_location(request: Request):
    if not is_local(request):
        raise HTTPException(403, "Solo dal display locale")
    body = await request.json()
    try:
        loc = await location.locator.report_browser(float(body["lat"]), float(body["lon"]),
                                                    float(body.get("accuracy") or 0))
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "Coordinate non valide")
    return {"ok": True, "name": loc.get("name")}


@admin_routes.get("/api/location")
async def admin_location(_: str = Depends(require_admin)):
    return {"current": await location.locator.current(), **location.locator.overview()}


@admin_routes.get("/api/location/search")
async def admin_location_search(q: str = "", _: str = Depends(require_admin)):
    try:
        return {"results": await location.search(q[:120])}
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, "Ricerca dei luoghi non disponibile")


@admin_routes.put("/api/location")
async def admin_location_set(request: Request, user: str = Depends(require_admin)):
    body = await request.json()
    try:
        if "name" in body or "lat" in body:
            await location.locator.set_default(body.get("name", ""), body.get("lat"), body.get("lon"), body.get("mode"))
        elif body.get("mode"):
            location.locator.set_mode(body["mode"])
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, f"Posizione non valida: {exc}")
    store.event("INFO", f"Posizione aggiornata da {user}", "location")
    return {"current": await location.locator.current(), **location.locator.overview()}
