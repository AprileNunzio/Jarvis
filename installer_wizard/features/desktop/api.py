import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from access import is_local, require_admin, require_display, require_internal
from features.desktop.desk import FILES, desk
from features.music import music
from features.spotify.spotify import spotify
from state import store

public_routes = APIRouter()
admin_routes = APIRouter()

desk.register_source("now_playing", music.watcher.current)
desk.register_source("spotify", spotify.current)


def _alert(body: dict) -> dict:
    kind = str(body.get("kind") or "generic")[:30]
    key = f"alarm:{kind}:{str(body.get('room') or '')[:40]}"
    if body.get("clear"):
        desk.hide(key=key)
        store.event("INFO", f"Allarme {kind} rientrato", "alarm")
        return {"ok": True, "cleared": key}
    data = {"kind": kind, "room": str(body.get("room") or "")[:60], "title": str(body.get("title") or "")[:80],
            "message": str(body.get("message") or "")[:300], "at": time.time()}
    where = ("in " + data["room"]) if data["room"] else ""
    data["speak"] = str(body.get("speak") or f"Attenzione! {data['title'] or 'Allarme'} {where}.")[:200]
    desk.show("alarm", data, key=key, priority=int(body.get("priority", 100)))
    store.event("ERROR", f"ALLARME {kind} {data['room']}: {data['message']}", "alarm")
    return {"ok": True, "key": key}


@public_routes.get("/widgets/{wid}/{name}")
async def widget_file(wid: str, name: str):
    path = desk.file(wid, name)
    if not path:
        raise HTTPException(404, "Widget non trovato")
    return FileResponse(path, media_type=FILES[name], headers={"Cache-Control": "no-cache"})


@public_routes.post("/api/desk/idle")
async def desk_idle(request: Request):
    require_display(request, "Solo dal display o dal pannello")
    desk.dismiss_intents()
    return {"ok": True}


@public_routes.post("/api/desk/position")
async def desk_position(request: Request):
    require_display(request, "Solo dal display")
    body = await request.json()
    wid = str(body.get("id") or "")
    try:
        if body.get("clear"):
            desk.set_position(wid, None, None)
        else:
            desk.set_position(wid, float(body.get("x")), float(body.get("y")))
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "Posizione non valida")
    return {"ok": True}


@public_routes.post("/api/desk/hello")
async def desk_hello(request: Request):
    require_display(request, "Solo dal display")
    body = await request.json()
    try:
        desk.screen_hello(max(0, min(16, int(body.get("screen", 0)))), int(body.get("x", 0)),
                          int(body.get("w", 0)), int(body.get("h", 0)),
                          bool(body.get("local")) and is_local(request), str(body.get("ear") or "")[:260],
                          str(body.get("perf") or "")[:420], request.client.host if request.client else "")
    except (TypeError, ValueError):
        raise HTTPException(400, "Schermo non valido")
    return {"ok": True}


@public_routes.post("/api/desk/screen")
async def desk_screen(request: Request):
    require_display(request, "Solo dal display")
    body = await request.json()
    wid, screen = str(body.get("id") or ""), body.get("screen")
    try:
        desk.set_screen(wid, None if screen is None else max(0, min(16, int(screen))))
    except KeyError:
        raise HTTPException(404, "Widget sconosciuto")
    except (TypeError, ValueError):
        raise HTTPException(400, "Schermo non valido")
    return {"ok": True}


@admin_routes.post("/api/alarm")
async def internal_alert(request: Request):
    require_internal(request)
    return _alert(await request.json())


@admin_routes.get("/api/widgets")
async def admin_widgets(_: str = Depends(require_admin)):
    desk.scan()
    return desk.listing()


@admin_routes.put("/api/widgets/{wid}")
async def admin_widget_set(wid: str, request: Request, _: str = Depends(require_admin)):
    try:
        desk.set_prefs(wid, await request.json())
    except KeyError:
        raise HTTPException(404, "Widget sconosciuto")
    except (TypeError, ValueError):
        raise HTTPException(400, "Valore non valido")
    return desk.listing()


@admin_routes.post("/api/widgets/{wid}/test")
async def admin_widget_test(wid: str, _: str = Depends(require_admin)):
    m = desk.widgets.get(wid)
    if not m:
        raise HTTPException(404, "Widget sconosciuto")
    if wid == "alarm":
        _alert({**m.get("demo", {}), "title": "Prova allarme", "message": "Questa è una prova dal pannello: nessun pericolo."})
        desk.instances[next(k for k in desk.instances if k.startswith("alarm:"))]["expires_at"] = time.time() + 20
    else:
        desk.show(wid, {**m.get("demo", {}), "started_at": time.time() - 30}, key=f"test:{wid}", ttl=30)
    return desk.listing()


@admin_routes.delete("/api/desk/{key:path}")
async def admin_desk_hide(key: str, _: str = Depends(require_admin)):
    desk.hide(key=key)
    return desk.listing()
