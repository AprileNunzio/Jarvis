import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from access import require_admin
from features.maps.maps import maps

admin_routes = APIRouter()


@admin_routes.get("/api/maps")
async def admin_maps(_: str = Depends(require_admin)):
    return maps.summary()


@admin_routes.put("/api/maps/places/{name}")
async def admin_maps_place(name: str, request: Request, _: str = Depends(require_admin)):
    address = str((await request.json()).get("address", "")).strip()
    if not address or not name.strip():
        raise HTTPException(400, "Nome e indirizzo obbligatori")
    try:
        await maps.save_place(name.strip()[:30], address[:200])
    except LookupError:
        raise HTTPException(404, f"Indirizzo non trovato: {address}")
    return maps.summary()


@admin_routes.delete("/api/maps/places/{name}")
async def admin_maps_place_delete(name: str, _: str = Depends(require_admin)):
    maps.delete_place(name)
    return maps.summary()


@admin_routes.post("/api/maps/test")
async def admin_maps_test(request: Request, _: str = Depends(require_admin)):
    dest = str((await request.json()).get("to", "")).strip()
    try:
        origin = await maps.home()
        target = await maps.resolve(dest)
        r = await maps.route(origin, target, maps.default_mode())
    except LookupError:
        raise HTTPException(404, f"Luogo non trovato: {dest}")
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(400, str(exc))
    return maps.card(origin, target, r)
