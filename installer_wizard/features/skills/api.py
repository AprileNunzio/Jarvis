from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse

from access import require_admin
from features.skills.library import library
from state import store

admin_routes = APIRouter()


@admin_routes.get("/api/skills")
async def admin_skills(_: str = Depends(require_admin)):
    return library.listing()


@admin_routes.get("/api/skills/{key:path}/code")
async def admin_skill_code(key: str, _: str = Depends(require_admin)):
    try:
        return PlainTextResponse(library.code(key))
    except KeyError:
        raise HTTPException(404, "Algoritmo sconosciuto")


@admin_routes.post("/api/skills/ask")
async def admin_skill_ask(request: Request, _: str = Depends(require_admin)):
    text = str((await request.json()).get("text", ""))[:500]
    return {"answer": await library.try_answer(text), "needs": library.needs_algorithm(text)}


@admin_routes.post("/api/skills/{key:path}/test")
async def admin_skill_test(key: str, request: Request, _: str = Depends(require_admin)):
    try:
        return await library.test(key, str((await request.json()).get("text", ""))[:500])
    except KeyError:
        raise HTTPException(404, "Algoritmo sconosciuto")


@admin_routes.put("/api/skills/{key:path}")
async def admin_skill_set(key: str, request: Request, _: str = Depends(require_admin)):
    try:
        library.set_enabled(key, bool((await request.json()).get("enabled", True)))
    except KeyError:
        raise HTTPException(404, "Algoritmo sconosciuto")
    return library.listing()


@admin_routes.delete("/api/skills/{key:path}")
async def admin_skill_delete(key: str, user: str = Depends(require_admin)):
    try:
        library.delete(key)
    except KeyError:
        raise HTTPException(404, "Algoritmo sconosciuto")
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    store.event("INFO", f"Algoritmo {key} eliminato da {user}", "skills")
    return library.listing()
