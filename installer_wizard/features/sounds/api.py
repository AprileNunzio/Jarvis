from fastapi import APIRouter, Depends, HTTPException, Request

from access import require_admin
from features.sounds.library import AMBIENTS, listing
from features.sounds.policy import policy

public_routes = APIRouter()
admin_routes = APIRouter()


@admin_routes.get("/api/sounds")
async def overview(_: str = Depends(require_admin)):
    return {"state": policy.state(), "sounds": listing(), "ambients": AMBIENTS, "scheduled": policy.scheduled()}


@admin_routes.post("/api/sounds/dnd")
async def dnd(request: Request, _: str = Depends(require_admin)):
    body = await request.json()
    if body.get("off"):
        return {"message": policy.clear_dnd()}
    minutes = body.get("minutes")
    return {"message": policy.set_dnd(float(minutes) if minutes else None, "pannello")}


@admin_routes.post("/api/sounds/play/{name}")
async def play(name: str, _: str = Depends(require_admin)):
    try:
        return {"message": policy.play(name, force=True, reason="prova dal pannello")}
    except ValueError as exc:
        raise HTTPException(404, str(exc))
