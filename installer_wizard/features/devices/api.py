from fastapi import APIRouter, Depends, Request

from access import require_admin, require_display
from features.devices import audio
from state import store

public_routes = APIRouter()
admin_routes = APIRouter()


@public_routes.get("/api/audio")
async def public_audio(request: Request):
    require_display(request)
    return await audio.status()


@public_routes.put("/api/audio")
async def public_audio_set(request: Request):
    require_display(request)
    return await audio.update(await request.json())


@admin_routes.get("/api/audio")
async def admin_audio(_: str = Depends(require_admin)):
    return await audio.status()


@admin_routes.put("/api/audio")
async def admin_audio_set(request: Request, user: str = Depends(require_admin)):
    result = await audio.update(await request.json())
    store.event("INFO", f"Audio modificato da {user}", "audio")
    return result
