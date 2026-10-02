import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request

from access import require_admin
from config import DEMO
from features.home_assistant import home
from features.home_assistant.connection import HAError
from state import store

admin_routes = APIRouter()


@admin_routes.get("/api/home")
async def admin_home(_: str = Depends(require_admin)):
    return home.brain.overview()


@admin_routes.get("/api/home/devices")
async def admin_home_devices(_: str = Depends(require_admin)):
    return home.brain.device_list()


@admin_routes.get("/api/home/activity")
async def admin_home_activity(hours: int = 24, _: str = Depends(require_admin)):
    return {"activity": home.brain.activity(max(1, min(hours, 24 * 30))), "commands": home.brain.commands()}


@admin_routes.post("/api/home/sync")
async def admin_home_sync(user: str = Depends(require_admin)):
    if not home.brain.online or DEMO:
        raise HTTPException(409, "Home Assistant non è collegato")
    try:
        await home.brain.sync(f"richiesto da {user}")
    except (HAError, asyncio.TimeoutError) as exc:
        raise HTTPException(502, f"Studio della casa non riuscito: {exc}")
    store.event("INFO", f"Casa ristudiata su richiesta di {user}: {home.brain.summary_line()}", "home")
    return home.brain.overview()


@admin_routes.post("/api/home/test")
async def admin_home_test(request: Request, _: str = Depends(require_admin)):
    body = await request.json()
    text = str(body.get("text", "")).strip()[:300]
    if not text:
        raise HTTPException(400, "Scrivi un comando")
    return await home.brain.test(text, bool(body.get("run")))


@admin_routes.put("/api/home/aliases")
async def admin_home_aliases(request: Request, _: str = Depends(require_admin)):
    body = await request.json()
    names = body.get("names") or []
    if isinstance(names, str):
        names = names.split(",")
    try:
        home.brain.set_aliases(str(body.get("target", "")), [str(n) for n in names])
    except KeyError:
        raise HTTPException(404, "Stanza o entità sconosciuta")
    return {"ok": True}


@admin_routes.delete("/api/home/learned")
async def admin_home_forget(user: str = Depends(require_admin)):
    home.brain.forget_learned()
    store.event("INFO", f"Frasi della casa imparate dimenticate da {user}", "home")
    return {"ok": True}
