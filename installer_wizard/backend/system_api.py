import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

import auth
import health
import updater
from access import NO_CACHE, require_admin, require_internal, session_user
from config import DEMO, EDITABLE_KEYS, JARVIS_DIR, NODE, SECRET_KEYS, read_env
from orchestrator import orch
from pages import page
from settings import apply_config
from snapshot import full_snapshot, sse
from state import INSTALL_LOG, store
from steps import STEP_BY_ID
from tasks import background, delayed

public_routes = APIRouter()
admin_routes = APIRouter()

LOG_SOURCES = {
    "install": "Installazione e step",
    "supervisor": "Supervisore (journal)",
    "core": "Jarvis Core (container)",
    "ollama": "Motore neurale",
    "kiosk": "Display kiosk",
    "rollback": "Rollback",
}
LOG_COMMANDS = {
    "install": lambda n: ("tail", "-n", n, str(INSTALL_LOG)),
    "supervisor": lambda n: ("journalctl", "-u", "jarvis-supervisor", "-n", n, "--no-pager"),
    "core": lambda n: ("docker", "logs", "--tail", n, "jarvis-core"),
    "ollama": lambda n: ("journalctl", "-u", "ollama", "-n", n, "--no-pager"),
    "kiosk": lambda n: ("tail", "-n", n, "/home/jarvis-kiosk/.cache/jarvis-kiosk.log"),
    "rollback": lambda n: ("tail", "-n", n, "/var/log/jarvis/rollback.log"),
}
COMPONENT_RESTART = {
    "core": ["docker", "restart", "jarvis-core"],
    "qdrant": ["docker", "restart", "jarvis-qdrant"],
    "ollama": ["systemctl", "restart", "ollama"],
    "docker": ["systemctl", "restart", "docker"],
    "kiosk": ["systemctl", "restart", "getty@tty1"],
}


@public_routes.get("/")
async def public_index(node: str = ""):
    if node:
        from features.nodes.registry import registry
        if node in registry.data["nodes"]:
            NODE.set(node)
    return page("display/display.html" if store.phase in ("READY", "DEGRADED") else "monitor/monitor.html")


@public_routes.get("/screen")
async def public_screen():
    return page("screen/screen.html" if store.phase in ("READY", "DEGRADED") else "monitor/monitor.html")


@public_routes.get("/healthz")
@admin_routes.get("/healthz")
async def healthz():
    return {"ok": True, "phase": store.phase}


@public_routes.get("/api/state")
async def public_state():
    return JSONResponse(full_snapshot(admin=False), headers=NO_CACHE)


public_routes.add_api_route("/api/stream", sse(admin=False), methods=["GET"])

from pydantic import BaseModel
class HoloActionReq(BaseModel):
    express: str = None
    play: str = None
    stop: str = None
    shot: str = None
    seconds: float = None
    dance: bool = None
    sing: bool = None
    accessory: dict = None

@public_routes.post("/api/holo_action")
async def trigger_holo_action(req: HoloActionReq):
    store.holo_action = req.dict(exclude_none=True)
    store.version += 1
    return {"ok": True}


@admin_routes.get("/")
async def admin_index():
    return page("admin/admin.html")


@admin_routes.post("/api/auth/login")
async def login(request: Request):
    if request.headers.get("X-Jarvis-Request") != "1":
        raise HTTPException(403, "Richiesta non valida")
    body = await request.json()
    ip = request.client.host if request.client else "?"
    username = str(body.get("username", "")).strip()
    if auth.rate_limited(ip):
        raise HTTPException(429, "Troppi tentativi: riprova tra qualche minuto")
    ok = await asyncio.to_thread(auth.authenticate, username, str(body.get("password", "")), ip)
    if not ok:
        store.event("WARN", f"Accesso admin negato per '{username}' da {ip}", "auth")
        raise HTTPException(401, "Credenziali non valide o utente non autorizzato")
    store.event("INFO", f"Accesso admin: {username} da {ip}", "auth")
    resp = JSONResponse({"user": username})
    resp.set_cookie(auth.SESSION_COOKIE, auth.issue(username), max_age=auth.SESSION_TTL,
                    httponly=True, samesite="strict")
    return resp


@admin_routes.post("/api/auth/logout")
async def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth.SESSION_COOKIE)
    return resp


@admin_routes.get("/api/auth/me")
async def me(request: Request):
    user = session_user(request)
    if not user:
        raise HTTPException(401, "Accesso richiesto")
    return {"user": user, "demo": DEMO}


@admin_routes.get("/api/state")
async def admin_state(_: str = Depends(require_admin)):
    return JSONResponse(full_snapshot(admin=True), headers=NO_CACHE)


@admin_routes.get("/api/stream")
async def admin_stream(request: Request, _: str = Depends(require_admin)):
    return await sse(admin=True)(request)


@admin_routes.get("/api/logs/{source}")
async def admin_logs(source: str, lines: int = 300, _: str = Depends(require_admin)):
    lines = max(20, min(lines, 3000))
    if source not in LOG_SOURCES:
        raise HTTPException(404, "Sorgente sconosciuta")
    if DEMO:
        return {"source": source, "text": "\n".join(e["msg"] for e in list(store.logs)[-lines:])}
    _, out = await health.sh(*LOG_COMMANDS[source](str(lines)))
    return {"source": source, "text": out}


@admin_routes.post("/api/actions/{action}")
async def admin_action(action: str, request: Request, user: str = Depends(require_admin)):
    body = {}
    if request.headers.get("content-type", "").startswith("application/json"):
        body = await request.json()
    store.event("INFO", f"Azione admin '{action}' da {user}", "admin")

    if action == "repair":
        background(orch.converge(reason="Riparazione completa richiesta dall'amministratore"))
    elif action == "rerun-step":
        step_id = body.get("step")
        if step_id not in STEP_BY_ID:
            raise HTTPException(404, "Step sconosciuto")
        background(orch.converge([step_id], reason=f"Riesecuzione: {STEP_BY_ID[step_id].title}", force=True))
    elif action == "restart-component":
        comp = body.get("component")
        if comp not in COMPONENT_RESTART:
            raise HTTPException(404, "Componente sconosciuto")
        if comp == "kiosk":
            await health.sh("pkill", "-t", "tty1")
        code, out = (0, "demo") if DEMO else await health.sh(*COMPONENT_RESTART[comp], timeout=180)
        return {"ok": code == 0, "output": out[-500:]}
    elif action == "update-check":
        return await updater.check()
    elif action == "update-apply":
        if not (await updater.check()).get("available"):
            return {"ok": False, "message": "Nessun aggiornamento disponibile"}
        background(updater.apply("manuale"))
    elif action == "reboot":
        background(delayed("systemctl", "reboot"))
    elif action == "restart-supervisor":
        background(delayed("systemctl", "restart", "jarvis-supervisor"))
    else:
        raise HTTPException(404, "Azione sconosciuta")
    return {"ok": True}


@admin_routes.post("/api/internal/{action}")
async def internal_action(action: str, request: Request):
    require_internal(request)
    store.event("INFO", f"Comando locale jarvisctl: {action}", "jarvisctl")
    if action == "update":
        info = await updater.check()
        if not info.get("available"):
            return {"ok": True, "message": f"Jarvis è aggiornato ({(info.get('local_rev') or '?')[:7]}). "
                                           f"{info.get('last_result', '')}".strip()}
        background(updater.apply("richiesto da jarvisctl"))
        return {"ok": True, "message": f"Aggiornamento {info['local_rev'][:7]} → {(info.get('target_rev') or info['remote_rev'])[:7]} avviato: "
                                       "il supervisore si riavvierà e verificherà la nuova versione."}
    if action == "repair":
        background(orch.converge(reason="Riparazione richiesta da jarvisctl"))
        return {"ok": True, "message": "Verifica e riparazione di tutti i componenti avviata."}
    raise HTTPException(404, "Azione sconosciuta")


@admin_routes.get("/api/config")
async def get_config(_: str = Depends(require_admin)):
    env = read_env()
    items = []
    for key, label in EDITABLE_KEYS.items():
        value = env.get(key, "")
        secret = key in SECRET_KEYS
        items.append({"key": key, "label": label, "secret": secret,
                      "value": ("••••" + value[-4:]) if (secret and value) else value, "set": bool(value)})
    readonly = {k: v for k, v in env.items() if k not in EDITABLE_KEYS}
    return {"editable": items, "system": readonly, "jarvis_dir": str(JARVIS_DIR)}


@admin_routes.put("/api/config")
async def put_config(request: Request, user: str = Depends(require_admin)):
    body = await request.json()
    updates = {k: str(v).strip() for k, v in body.items() if k in EDITABLE_KEYS}
    updates = {k: v for k, v in updates.items() if not (k in SECRET_KEYS and v.startswith("••••"))}
    if not updates:
        return {"ok": True, "changed": []}
    needs = await apply_config(updates, user)
    return {"ok": True, "changed": list(updates), "applying": needs}
