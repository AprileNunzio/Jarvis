from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from access import require_admin, require_display
from features.models3d import convert, generator, library
from state import store

public_routes = APIRouter()
admin_routes = APIRouter()

TYPES = {"glb": "model/gltf-binary", "gltf": "model/gltf+json", "stl": "model/stl", "obj": "text/plain",
         "mtl": "text/plain", "dxf": "text/plain", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}


def _meta(mid: str) -> dict:
    try:
        return library.get(mid)
    except KeyError:
        raise HTTPException(404, "Modello sconosciuto")


@public_routes.get("/api/models3d")
async def models_list(request: Request):
    require_display(request, "Solo dal display")
    return {"models": library.listing(), "formats": library.FORMATS}


@public_routes.get("/api/models3d/{mid}/{name}")
async def model_file(mid: str, name: str, request: Request):
    require_display(request, "Solo dal display")
    try:
        path = library.path(mid, name)
    except KeyError:
        raise HTTPException(404, "File sconosciuto")
    return FileResponse(path, media_type=TYPES.get(library.ext_of(name), "application/octet-stream"),
                        filename=path.name, headers={"Cache-Control": "no-cache"})


@public_routes.post("/api/models3d/{mid}/show")
async def model_show(mid: str, request: Request):
    require_display(request, "Solo dal display")
    library.show(_meta(mid))
    return {"ok": True}


@admin_routes.get("/api/models3d")
async def admin_models(_: str = Depends(require_admin)):
    return {"models": library.listing(), "formats": library.FORMATS,
            "converters": {fmt: bool(convert.tool(fmt)) for fmt in convert.NEEDS}}


@admin_routes.post("/api/models3d/upload")
async def admin_upload(request: Request, name: str, id: str = "", user: str = Depends(require_admin)):
    fmt = library.ext_of(name)
    if fmt not in library.FORMATS and fmt not in ("bin", "png", "jpg", "jpeg"):
        raise HTTPException(400, f"Formato .{fmt} non supportato")
    data = await request.body()
    meta = _meta(id) if id else library.create(name.rsplit(".", 1)[0], "user")
    try:
        meta = library.add_file(meta, name, data, main=fmt in library.FORMATS and fmt != "mtl")
    except ValueError as exc:
        raise HTTPException(413, str(exc))
    if convert.needs_conversion(fmt):
        meta = await convert.convert(meta, library.safe_name(name))
    store.event("INFO", f"Modello 3D caricato da {user}: {name}", "models3d")
    library.show(meta)
    return meta


@admin_routes.post("/api/models3d/generate")
async def admin_generate(request: Request, _: str = Depends(require_admin)):
    subject = str((await request.json()).get("subject", "")).strip()[:200]
    if not subject:
        raise HTTPException(400, "Dimmi cosa modellare")
    try:
        meta = await generator.create(subject)
    except ValueError as exc:
        raise HTTPException(502, str(exc))
    library.show(meta, f"Ecco {meta['title']} in 3D.")
    return meta


@admin_routes.get("/api/models3d/{mid}/{name}")
async def admin_file(mid: str, name: str, _: str = Depends(require_admin)):
    try:
        path = library.path(mid, name)
    except KeyError:
        raise HTTPException(404, "File sconosciuto")
    return FileResponse(path, media_type=TYPES.get(library.ext_of(name), "application/octet-stream"), filename=path.name)


@admin_routes.post("/api/models3d/{mid}/show")
async def admin_show(mid: str, _: str = Depends(require_admin)):
    library.show(_meta(mid))
    return {"ok": True}


@admin_routes.delete("/api/models3d/{mid}")
async def admin_delete(mid: str, _: str = Depends(require_admin)):
    _meta(mid)
    library.remove(mid)
    return {"ok": True}
