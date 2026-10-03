import json
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

import health
from access import require_admin
from config import DEMO, ollama_url, read_env, write_env
from feature_registry import registry
from features.brain import assignments_api, bridge
from features.brain.brains import brains
from features.brain.residency import rebalance
from features.brain.roles import ROLES
from state import store
from tasks import background

admin_routes = APIRouter()
admin_routes.include_router(assignments_api.admin_routes)
admin_routes.include_router(bridge.admin_routes)
public_routes = assignments_api.public_routes
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,119}$")


async def pull_model(name: str) -> None:
    store.model_pull = {"name": name, "status": "avvio", "percent": 0}
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{ollama_url()}/api/pull", json={"model": name}) as resp:
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    msg = json.loads(line)
                    if "error" in msg:
                        raise RuntimeError(msg["error"])
                    pct = int(msg["completed"] * 100 / msg["total"]) if msg.get("total") and msg.get("completed") else None
                    store.model_pull = {"name": name, "status": msg.get("status", ""),
                                        "percent": pct if pct is not None else store.model_pull["percent"]}
                    store.touch()
        store.model_pull = {"name": name, "status": "completato", "percent": 100}
        store.event("INFO", f"Modello scaricato: {name}", "models")
        brains.invalidate()
    except Exception as exc:
        store.model_pull = {"name": name, "status": f"errore: {exc}", "percent": 0}
        store.event("ERROR", f"Download modello {name} non riuscito: {exc}", "models")
    store.touch()


@admin_routes.get("/api/models")
async def list_models(_: str = Depends(require_admin)):
    if DEMO:
        return {"models": [{"name": "qwen2.5:3b", "size": 1_900_000_000}], "loaded": ["qwen2.5:3b"]}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            tags = (await client.get(f"{ollama_url()}/api/tags")).json().get("models", [])
            loaded = [m["name"] for m in (await client.get(f"{ollama_url()}/api/ps")).json().get("models", [])]
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, "Motore neurale non raggiungibile")
    return {"models": [{"name": m["name"], "size": m.get("size", 0), "modified": m.get("modified_at")}
                       for m in tags], "loaded": loaded}


@admin_routes.post("/api/models/pull")
async def admin_pull(request: Request, _: str = Depends(require_admin)):
    name = str((await request.json()).get("name", "")).strip()
    if not name or len(name) > 120 or any(c.isspace() for c in name):
        raise HTTPException(400, "Nome modello non valido")
    background(pull_model(name))
    return {"ok": True}


@admin_routes.delete("/api/models/{name:path}")
async def admin_delete_model(name: str, _: str = Depends(require_admin)):
    env, cfg = read_env(), brains.config()
    in_use = {health.norm_model(m) for m in [env.get("JARVIS_LLM_MODEL", ""), env.get("JARVIS_EMBED_MODEL", ""),
                                             cfg["fast"], *(m for role in ROLES for m in cfg[role.id])] if m}
    if health.norm_model(name) in in_use:
        raise HTTPException(409, "Il modello è in uso: toglilo prima dalle liste del cervello")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.request("DELETE", f"{ollama_url()}/api/delete", json={"model": name})
    brains.invalidate()
    return {"ok": r.status_code == 200}


@admin_routes.get("/api/brains")
async def admin_brains(_: str = Depends(require_admin)):
    if not registry.hw:
        await registry.probe_hardware()
    return await brains.overview(registry.hw)


@admin_routes.put("/api/brains")
async def admin_brains_set(request: Request, user: str = Depends(require_admin)):
    body, updates = await request.json(), {}
    if "routing" in body:
        if body["routing"] not in ("auto", "1", "0"):
            raise HTTPException(400, "Modalità di instradamento non valida")
        updates["JARVIS_LLM_ROUTING"] = body["routing"]
    for role in ROLES:
        if role.id in body:
            models = [str(m).strip() for m in (body[role.id] or []) if str(m).strip()]
            if len(models) > 12 or not all(_MODEL_RE.match(m) for m in models):
                raise HTTPException(400, "Elenco di modelli non valido")
            updates[role.env_key] = ",".join(dict.fromkeys(models))
    if updates:
        write_env(updates)
        brains.invalidate()
        background(rebalance())
        store.event("INFO", f"Cervello aggiornato da {user}: {', '.join(updates)}", "models")
    return await brains.overview(registry.hw)


@admin_routes.post("/api/brains/test")
async def admin_brains_test(request: Request, _: str = Depends(require_admin)):
    text = str((await request.json()).get("text", ""))[:2000]
    return await brains.route(text)


@admin_routes.post("/api/brains/ollama/test")
async def admin_ollama_test(request: Request, _: str = Depends(require_admin)):
    from settings import normalize_ollama
    raw = str((await request.json()).get("url", "")).strip()
    url = normalize_ollama(raw) if raw else "http://127.0.0.1:11434"
    try:
        async with httpx.AsyncClient(timeout=6) as client:
            version = (await client.get(f"{url}/api/version")).json().get("version", "?")
            tags = (await client.get(f"{url}/api/tags")).json().get("models", [])
    except (httpx.HTTPError, ValueError) as exc:
        return {"ok": False, "url": url, "error": f"non raggiungibile ({type(exc).__name__}): sul server remoto avvia Ollama con OLLAMA_HOST=0.0.0.0"}
    return {"ok": True, "url": url, "version": version, "models": [m.get("name", "") for m in tags]}


@admin_routes.get("/api/projects/status")
async def get_projects_status(_: str = Depends(require_admin)):
    import os, json
    projects_dir = "data/projects"
    running = []
    if os.path.exists(projects_dir):
        for f in os.listdir(projects_dir):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(projects_dir, f), "r", encoding="utf-8") as file:
                        data = json.load(file)
                        if data.get("status") in ["running", "paused"]:
                            running.append(data)
                except:
                    pass
    return {"projects": running}
