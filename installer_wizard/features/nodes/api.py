import hashlib
import time

from access import require_admin
from config import EDITABLE_KEYS, JARVIS_DIR, NODE, node_keys, read_global_env
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from state import store

from features.nodes import server
from features.nodes.beacon import beacon
from features.nodes.requests import requests
from features.nodes.registry import COMMANDS, TYPES, registry

public_routes = APIRouter()
admin_routes = APIRouter()
_failures: dict[str, list[float]] = {}


def _ip(request: Request) -> str:
    return request.client.host if request.client else "?"


def _limited(ip: str) -> bool:
    recent = [t for t in _failures.get(ip, []) if time.time() - t < 300]
    _failures[ip] = recent
    return len(recent) >= 5


async def _body(request: Request) -> dict:
    if int(request.headers.get("content-length") or 0) > 16384:
        raise HTTPException(413, "Richiesta troppo grande")
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(400, "Richiesta non valida")
    return body


@public_routes.post("/api/nodes/pair")
async def node_pair(request: Request):
    ip = _ip(request)
    if _limited(ip):
        raise HTTPException(429, "Troppi tentativi: riprova tra qualche minuto")
    body = await _body(request)
    try:
        token = registry.pair(str(body.get("code", "")), body.get("id"), body)
    except PermissionError as exc:
        _failures.setdefault(ip, []).append(time.time())
        store.event("WARN", f"Abbinamento nodo rifiutato da {ip}", "nodes")
        raise HTTPException(403, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    store.event("INFO", f"Nuovo nodo abbinato: {body.get('name') or body.get('id')} ({ip})", "nodes")
    return {"token": token, "heartbeat": 30}


@public_routes.post("/api/nodes/heartbeat")
async def node_heartbeat(request: Request):
    body = await _body(request)
    auth = request.headers.get("authorization", "")
    try:
        node = registry.authenticate(request.headers.get("x-jarvis-node", ""), auth.removeprefix("Bearer ").strip())
    except PermissionError as exc:
        raise HTTPException(401, str(exc))
    was_online = time.time() - node.get("last_seen", 0) < 90
    commands = registry.heartbeat(node, body, _ip(request))
    if not was_online:
        store.event("INFO", f"Nodo online: {node['name']}", "nodes")
    return {"commands": commands, "heartbeat": 30, "agent": _agent_sha(), "settings": registry.effective(node["id"]),
            "custom": sorted(node.get("settings") or {})}


def _agent_path():
    return JARVIS_DIR / "client_satellite" / "linux_edge" / "satellite.py"


def _agent_sha() -> str:
    try:
        return hashlib.sha256(_agent_path().read_bytes()).hexdigest()
    except OSError:
        return ""


@public_routes.post("/api/nodes/request")
async def node_request(request: Request):
    ip = _ip(request)
    if _limited(ip):
        raise HTTPException(429, "Troppi tentativi: riprova tra qualche minuto")
    body = await _body(request)
    try:
        result = requests.submit(body, ip)
    except PermissionError as exc:
        _failures.setdefault(ip, []).append(time.time())
        raise HTTPException(409, str(exc))
    except ValueError as exc:
        _failures.setdefault(ip, []).append(time.time())
        raise HTTPException(400, str(exc))
    store.event("INFO", f"Il nodo {body.get('name') or body.get('id')} ({ip}) chiede di unirsi: codice {result['fingerprint']}",
                "nodes")
    return result


@public_routes.post("/api/nodes/claim")
async def node_claim(request: Request):
    ip = _ip(request)
    if _limited(ip):
        raise HTTPException(429, "Troppi tentativi: riprova tra qualche minuto")
    body = await _body(request)
    try:
        token = requests.claim(str(body.get("id") or ""), str(body.get("key") or ""))
    except PermissionError as exc:
        _failures.setdefault(ip, []).append(time.time())
        raise HTTPException(403, str(exc))
    return {"approved": bool(token), "token": token, "heartbeat": 30} if token else {"approved": False}


@admin_routes.get("/api/nodes")
async def nodes_overview(_: str = Depends(require_admin)):
    paired = {n["id"] for n in registry.listing()}
    return {"master": server.master(), "nodes": registry.listing(), "types": TYPES, "commands": COMMANDS,
            "pending": requests.listing(), "found": [f for f in beacon.found() if f["id"] not in paired]}


@admin_routes.post("/api/nodes/requests/{node_id}/approve")
async def nodes_approve(node_id: str, user: str = Depends(require_admin)):
    try:
        req = requests.approve(node_id)
    except KeyError:
        raise HTTPException(404, "Richiesta scaduta o inesistente")
    except (PermissionError, ValueError) as exc:
        raise HTTPException(400, str(exc))
    store.event("INFO", f"Nodo {req['name']} approvato da {user}", "nodes")
    return {"ok": True}


@admin_routes.delete("/api/nodes/requests/{node_id}")
async def nodes_reject(node_id: str, user: str = Depends(require_admin)):
    requests.reject(node_id)
    store.event("INFO", f"Richiesta del nodo {node_id} rifiutata da {user}", "nodes")
    return {"ok": True}


@admin_routes.post("/api/nodes/pairing-code")
async def nodes_code(user: str = Depends(require_admin)):
    store.event("INFO", f"Codice di abbinamento nodi generato da {user}", "nodes")
    return registry.new_code()


@admin_routes.put("/api/nodes/{node_id}")
async def nodes_update(node_id: str, request: Request, _: str = Depends(require_admin)):
    try:
        registry.update(node_id, await _body(request))
    except KeyError as exc:
        raise HTTPException(404, f"Nodo non trovato: {exc}")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"nodes": registry.listing()}


@admin_routes.get("/api/nodes/{node_id}/settings")
async def nodes_settings(node_id: str, _: str = Depends(require_admin)):
    try:
        node = registry.data["nodes"][node_id]
    except KeyError:
        raise HTTPException(404, "Nodo non trovato")
    env, custom = read_global_env(), node.get("settings") or {}
    return {"node": {k: v for k, v in node.items() if k != "token"},
            "items": [{"key": k, "label": EDITABLE_KEYS[k], "global": env.get(k, ""), "value": custom.get(k, ""),
                       "custom": k in custom} for k in node_keys()]}


@public_routes.post("/api/nodes/chat")
async def node_chat(request: Request):
    body = await _body(request)
    auth = request.headers.get("authorization", "")
    try:
        node = registry.authenticate(request.headers.get("x-jarvis-node", ""), auth.removeprefix("Bearer ").strip())
    except PermissionError as exc:
        raise HTTPException(401, str(exc))
    from features.chat.api import assistant_chat
    NODE.set(node["id"])
    return await assistant_chat(str(body.get("text", "")), node["id"], str(body.get("lang") or "") or None)


@admin_routes.post("/api/nodes/{node_id}/command/{command}")
async def nodes_command(node_id: str, command: str, user: str = Depends(require_admin)):
    try:
        registry.command(node_id, command)
    except KeyError:
        raise HTTPException(404, "Nodo non trovato")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    store.event("INFO", f"Comando «{COMMANDS[command]}» al nodo {node_id} da {user}", "nodes")
    return {"ok": True}


@admin_routes.delete("/api/nodes/{node_id}")
async def nodes_remove(node_id: str, user: str = Depends(require_admin)):
    try:
        registry.remove(node_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    store.event("INFO", f"Nodo {node_id} rimosso da {user}: il suo token non vale più", "nodes")
    return {"nodes": registry.listing()}


@public_routes.get("/nodes/agent.py")
async def node_agent():
    path = _agent_path()
    if not path.is_file():
        raise HTTPException(404, "Agente non disponibile")
    return FileResponse(path, media_type="text/x-python", filename="jarvis-node.py")
