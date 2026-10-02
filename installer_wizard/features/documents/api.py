from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from access import require_admin, require_display
from features.documents import jobs
from features.shares import archive

public_routes = APIRouter()
admin_routes = APIRouter()
MEDIA = {".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
         ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
         ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
         ".odt": "application/vnd.oasis.opendocument.text", ".ods": "application/vnd.oasis.opendocument.spreadsheet",
         ".odp": "application/vnd.oasis.opendocument.presentation", ".pdf": "application/pdf"}


def _entry(eid: str) -> dict:
    entry = jobs.load().get(eid)
    if not entry:
        raise HTTPException(404, "Documento sconosciuto")
    return entry


@public_routes.get("/api/documents/{eid}/preview.pdf")
async def preview(eid: str, request: Request):
    require_display(request)
    name = _entry(eid).get("preview")
    path = jobs.PREVIEWS / name if name else None
    if not path or not path.is_file():
        raise HTTPException(404, "Anteprima non disponibile")
    return FileResponse(path, media_type="application/pdf", headers={"Cache-Control": "no-store"})


@public_routes.get("/api/documents/{eid}/file/{n}")
async def file(eid: str, n: int, request: Request):
    require_display(request)
    files = _entry(eid)["files"]
    if not 0 <= n < len(files):
        raise HTTPException(404, "File sconosciuto")
    path = (archive.ROOT / files[n]).resolve()
    if not path.is_relative_to(archive.ROOT.resolve()) or not path.is_file():
        raise HTTPException(404, "File non trovato")
    return FileResponse(path, media_type=MEDIA.get(path.suffix, "application/octet-stream"), filename=path.name)


@admin_routes.get("/api/documents")
async def listing(_: str = Depends(require_admin)):
    items = sorted(jobs.load().values(), key=lambda e: e.get("created", 0), reverse=True)
    from features.documents import convert, recipes
    return {"items": items[:100], "root": str(archive.path("documenti")), "office": bool(convert.office()),
            "recipes": recipes.overview()}


@admin_routes.post("/api/documents")
async def create(request: Request, _: str = Depends(require_admin)):
    from features.documents.commands import _job
    from tasks import background
    text = str((await request.json()).get("request", "")).strip()
    if len(text) < 8:
        raise HTTPException(400, "Descriva il documento da preparare")
    background(_job(text))
    return {"ok": True}
