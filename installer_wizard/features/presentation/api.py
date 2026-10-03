from access import require_display
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from features.presentation.composition import image_store

public_routes = APIRouter()
_CACHE = {"Cache-Control": "private, max-age=86400"}


@public_routes.get("/api/presentation/image/{name}")
async def presentation_image(name: str, request: Request):
    require_display(request)
    path = image_store.path(name)
    if path is None:
        raise HTTPException(404, "Immagine non trovata")
    return FileResponse(path, media_type="image/png", headers=_CACHE)
