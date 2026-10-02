import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from access import require_admin
from features.spotify.spotify import spotify
from state import store

admin_routes = APIRouter()


@admin_routes.get("/api/spotify")
async def admin_spotify(_: str = Depends(require_admin)):
    return spotify.summary()


@admin_routes.post("/api/spotify/auth-url")
async def admin_spotify_url(_: str = Depends(require_admin)):
    try:
        return {"url": spotify.auth_url()}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@admin_routes.post("/api/spotify/finish")
async def admin_spotify_finish(request: Request, _: str = Depends(require_admin)):
    try:
        user = await spotify.finish(str((await request.json()).get("url", "")))
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(400, str(exc))
    return {**spotify.summary(), "user": user}


@admin_routes.delete("/api/spotify")
async def admin_spotify_disconnect(user: str = Depends(require_admin)):
    spotify.disconnect()
    store.event("INFO", f"Spotify scollegato da {user}", "spotify")
    return spotify.summary()
