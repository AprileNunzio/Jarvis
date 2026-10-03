import hashlib

from access import require_admin
from config import JARVIS_DIR
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response

from features.nodes.registry import registry
from features.rpa.broker import broker
from features.rpa.service import allowed_nodes, rpa

public_routes = APIRouter()
admin_routes = APIRouter()

POLL_WAIT = 20.0
MAX_BODY = 12 * 1024 * 1024
DAEMON = JARVIS_DIR / "client_satellite/linux_edge/rpa_daemon.py"


def _daemon_sha() -> str:
    try:
        return hashlib.sha256(DAEMON.read_bytes()).hexdigest()
    except OSError:
        return ""


def _node(request: Request) -> dict:
    token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    try:
        node = registry.authenticate(request.headers.get("x-jarvis-node", ""), token)
    except PermissionError as exc:
        raise HTTPException(401, str(exc))
    if not rpa.permitted(node["id"]):
        raise HTTPException(403, "Controllo del computer non abilitato per questo nodo")
    return node


async def _body(request: Request) -> dict:
    if int(request.headers.get("content-length") or 0) > MAX_BODY:
        raise HTTPException(413, "Richiesta troppo grande")
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(400, "Richiesta non valida")
    return body


@public_routes.post("/api/nodes/rpa/poll")
async def node_poll(request: Request):
    node = _node(request)
    broker.note_poll(node["id"], await _body(request))
    instruction = await broker.poll(node["id"], POLL_WAIT)
    return {"instruction": instruction, "update": _daemon_sha()}


@public_routes.post("/api/nodes/rpa/result")
async def node_result(request: Request):
    node = _node(request)
    result = await _body(request)
    if not broker.complete(node["id"], result):
        raise HTTPException(409, "Nessuna istruzione in attesa con questo identificativo")
    return {"ok": True}


@public_routes.get("/nodes/rpa_daemon.py")
async def node_daemon():
    if not DAEMON.exists():
        raise HTTPException(404, "Demone non disponibile")
    return FileResponse(DAEMON, media_type="text/x-python")


@admin_routes.get("/api/rpa/nodes")
async def rpa_nodes(_: str = Depends(require_admin)):
    return {"allowed": sorted(allowed_nodes()), "online": {n: broker.info(n) for n in broker.known()}}


@admin_routes.post("/api/rpa/run")
async def rpa_run(request: Request, user: str = Depends(require_admin)):
    body = await _body(request)
    try:
        trace = await rpa.run(str(body.get("node_id", "")), body.get("steps"), user)
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    return trace.to_dict()


@admin_routes.get("/api/rpa/screenshot/{node_id}.png")
async def rpa_screenshot(node_id: str, _: str = Depends(require_admin)):
    frame = broker.last_frame.get(node_id)
    if not frame:
        raise HTTPException(404, "Nessuna cattura disponibile")
    return Response(frame, media_type="image/png", headers={"Cache-Control": "no-store"})
