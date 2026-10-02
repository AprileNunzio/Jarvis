import httpx
from access import require_admin
from fastapi import APIRouter, Depends, HTTPException, Request
from state import store

from features.google.gservices import google
from features.people import people

admin_routes = APIRouter()


def _person(slug: str) -> dict:
    profile = people.load(slug)
    if not profile:
        raise HTTPException(404, "Persona non trovata")
    return profile


@admin_routes.get("/api/google")
async def admin_google(_: str = Depends(require_admin)):
    return google.summary()


@admin_routes.get("/api/google/{slug}/preview")
async def admin_google_preview(slug: str, _: str = Depends(require_admin)):
    _person(slug)
    return await google.preview(slug)


@admin_routes.post("/api/google/{slug}/auth-url")
async def admin_google_url(slug: str, request: Request, _: str = Depends(require_admin)):
    _person(slug)
    body = await request.json() if int(request.headers.get("content-length") or 0) else {}
    try:
        return {"url": google.auth_url(slug, [str(s) for s in body.get("services") or []])}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@admin_routes.post("/api/google/finish")
async def admin_google_finish(request: Request, user: str = Depends(require_admin)):
    try:
        slug, email = await google.link(str((await request.json()).get("url", ""))[:4000])
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(400, str(exc))
    store.event("INFO", f"Account Google di {slug} collegato da {user}", "google")
    return {**google.summary(), "linked": slug, "email": email}


@admin_routes.delete("/api/google/{slug}")
async def admin_google_disconnect(slug: str, user: str = Depends(require_admin)):
    _person(slug)
    await google.unlink(slug)
    store.event("INFO", f"Account Google di {slug} scollegato da {user}", "google")
    return google.summary()
