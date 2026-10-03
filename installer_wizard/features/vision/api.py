import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from access import require_admin, require_display
from features.people import people
from features.people.api import sync_person_neuron
from features.vision import stills
from features.vision.proxy import vision_proxy, vision_stream
from state import store
from tasks import background

public_routes = APIRouter()
admin_routes = APIRouter()


@public_routes.get("/api/vision/snapshot.jpg")
async def public_snapshot(request: Request):
    require_display(request)
    return await vision_proxy("/snapshot.jpg")


@public_routes.get("/api/vision/still/{sid}.jpg")
async def public_still(sid: str, request: Request):
    require_display(request)
    data = stills.get(sid) if re.fullmatch(r"[0-9a-f]{16}", sid) else None
    if not data:
        raise HTTPException(404, "Immagine non più disponibile")
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=600"})


@public_routes.get("/api/vision/live.mjpg")
async def public_live(request: Request):
    require_display(request)
    return await vision_stream("/live.mjpg")


@public_routes.get("/api/vision/hands.mjpg")
async def public_hands(request: Request):
    require_display(request)
    return await vision_stream("/hands.mjpg")


@admin_routes.get("/api/vision/stream.mjpg")
async def admin_vision_stream(_: str = Depends(require_admin)):
    return await vision_stream()


@admin_routes.get("/api/vision/people")
async def admin_people(_: str = Depends(require_admin)):
    return await vision_proxy("/people")


@admin_routes.get("/api/vision/people/{slug}/photo.jpg")
async def admin_person_photo(slug: str, _: str = Depends(require_admin)):
    return await vision_proxy(f"/people/{slug}/photo.jpg")


@admin_routes.post("/api/vision/people")
async def admin_enroll(request: Request, user: str = Depends(require_admin)):
    name = str((await request.json()).get("name", "")).strip()
    resp = await vision_proxy("/people", "POST", {"name": name}, timeout=30)
    if resp.status_code == 200:
        slug = json.loads(resp.body)["slug"]
        people.ensure(slug, name)
        background(sync_person_neuron(slug))
        store.event("INFO", f"Volto registrato per '{name}' da {user}", "vision")
    return resp


@admin_routes.delete("/api/vision/people/{slug}")
async def admin_forget(slug: str, user: str = Depends(require_admin)):
    resp = await vision_proxy(f"/people/{slug}", "DELETE")
    if resp.status_code == 200:
        store.event("INFO", f"Volto eliminato: {slug} (da {user})", "vision")
    return resp
