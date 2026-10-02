from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from features.actions.common import SITES_DIR

public_routes = APIRouter()


@public_routes.get("/siti/{name}/{path:path}")
async def site_file(name: str, path: str = ""):
    root = (SITES_DIR / name).resolve()
    target = (root / (path or "index.html")).resolve()
    if not root.is_relative_to(SITES_DIR.resolve()) or not target.is_relative_to(root) or not target.is_file():
        raise HTTPException(404, "Pagina non trovata")
    return FileResponse(target, headers={"Cache-Control": "no-cache"})


@public_routes.get("/siti/{name}")
async def site_root(name: str):
    return Response(status_code=307, headers={"Location": f"/siti/{name}/"})
