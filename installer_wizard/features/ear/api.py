import time

from fastapi import APIRouter, Request

from access import require_display
from config import env_get
from features.desktop.desk import desk
from state import store

public_routes = APIRouter()
admin_routes = APIRouter()
desk.register_source("ear_widget", lambda: {"ear": True} if env_get("JARVIS_EAR", "1") != "0" else None)


@public_routes.post("/api/ear/client")
async def ear_client(request: Request):
    require_display(request, "Solo dal display")
    body = await request.json()
    error = str(body.get("error") or "")[:160]
    previous = getattr(store, "mic", None) or {}
    store.mic = {"ok": bool(body.get("ok")), "error": error, "inputs": int(body.get("inputs") or 0),
                 "label": str(body.get("label") or "")[:80], "at": time.time()}
    if error and error != previous.get("error"):
        store.event("WARN", f"Microfono del display: {error}", "ear")
    elif body.get("ok") and previous.get("error"):
        store.event("INFO", f"Microfono del display di nuovo attivo: {store.mic['label'] or 'predefinito'}", "ear")
    return {"ok": True}
