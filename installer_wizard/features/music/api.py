from fastapi import APIRouter, Depends, HTTPException, Request

from access import require_admin, require_internal
from config import write_env
from features.music import music
from orchestrator import orch
from state import store
from tasks import background

admin_routes = APIRouter()


def overview() -> dict:
    step = store.steps.get("music") or {}
    return {**music.watcher.summary(), "step": {"status": step.get("status"), "error": step.get("error", "")}}


@admin_routes.get("/api/music")
async def admin_music(_: str = Depends(require_admin)):
    return overview()


@admin_routes.put("/api/music")
async def admin_music_set(request: Request, user: str = Depends(require_admin)):
    enabled = bool((await request.json()).get("enabled"))
    write_env({"JARVIS_MUSIC_ID": "1" if enabled else "0"})
    if not enabled:
        store.now_playing = {}
        store.touch()
    store.event("INFO", f"Riconoscimento musicale {'attivato' if enabled else 'disattivato'} da {user}", "music")
    background(orch.converge(["music"], reason="Riconoscimento musicale", force=enabled))
    return overview()


@admin_routes.post("/api/internal/music")
async def internal_music(request: Request):
    require_internal(request)
    wav = await request.body()
    if not 1000 < len(wav) < 4_000_000:
        raise HTTPException(400, "Audio non valido")
    return await music.watcher.handle(wav)
