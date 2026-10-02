import re

from access import require_admin
from config import write_env
from fastapi import APIRouter, Depends, HTTPException, Request
from state import store

from features.brain.brains import brains
from features.cloud import models, servers
from features.cloud.catalog import BY_ID, OPTION_CHOICES, PROVIDERS, make_ref
from features.cloud.client import CloudError, complete
from features.cloud.vault import vault
from tasks import background

admin_routes = APIRouter()
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+\-]{0,159}$")


def _provider(pid: str):
    spec = BY_ID.get(pid)
    if not spec:
        raise HTTPException(404, "Fornitore sconosciuto")
    return spec


def _describe(spec) -> dict:
    return {"id": spec.id, "name": spec.name, "kind": spec.kind, "base_url": spec.base_url, "key_url": spec.key_url,
            "needs_url": spec.needs_url, "key_optional": spec.key_optional, "reasoning": spec.reasoning,
            "notes": spec.notes, "configured": vault.configured(spec.id), **vault.public(spec.id)}


@admin_routes.get("/api/cloud")
async def cloud_overview(_: str = Depends(require_admin)):
    cfg = brains.config()
    return {"providers": [_describe(p) for p in PROVIDERS], "choices": OPTION_CHOICES,
            "chat": cfg["chat"], "deep": cfg["deep"]}


@admin_routes.put("/api/cloud/{pid}")
async def cloud_update(pid: str, request: Request, user: str = Depends(require_admin)):
    _provider(pid)
    body = await request.json()
    changes = {k: body[k] for k in ("key", "base_url", "enabled", "options") if k in body}
    try:
        vault.update(pid, changes)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    brains.invalidate()
    store.event("INFO", f"Cervello cloud {pid} aggiornato da {user}: {', '.join(changes)}", "cloud")
    return _describe(BY_ID[pid])


@admin_routes.get("/api/cloud/{pid}/models")
async def cloud_models(pid: str, refresh: bool = False, _: str = Depends(require_admin)):
    _provider(pid)
    return await models.available(pid, refresh)


@admin_routes.post("/api/cloud/{pid}/test")
async def cloud_test(pid: str, request: Request, _: str = Depends(require_admin)):
    spec = _provider(pid)
    fallback = vault.get(pid).get("model") or (spec.models[0] if spec.models else "")
    model = str((await request.json()).get("model") or fallback)
    if not _MODEL_RE.match(model):
        raise HTTPException(400, "Nome del modello non valido")
    try:
        reply = await complete(make_ref(pid, model), [{"role": "user", "content": "Rispondi solo: pronto."}],
                               max_tokens=400)
    except CloudError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "reply": reply.text[:200], "ms": round(reply.ms)}


@admin_routes.post("/api/cloud/only")
async def cloud_only(request: Request, user: str = Depends(require_admin)):
    body = await request.json()
    lists = {}
    for kind, key in (("chat", "JARVIS_LLM_CHAT_ORDER"), ("deep", "JARVIS_LLM_DEEP_ORDER")):
        refs = [str(r) for r in body.get(kind) or []]
        if not refs or len(refs) > 12 or not all(r.startswith("cloud:") and _MODEL_RE.match(r[6:]) for r in refs):
            raise HTTPException(400, "Scegli almeno un modello cloud per ogni lista")
        lists[key] = ",".join(dict.fromkeys(refs))
    write_env(lists)
    brains.invalidate()
    from features.brain.residency import rebalance
    background(rebalance())
    store.event("INFO", f"Jarvis usa solo cervelli cloud (impostato da {user})", "cloud")
    return {"ok": True}


@admin_routes.get("/api/brains/servers")
async def servers_list(_: str = Depends(require_admin)):
    cfg = brains.config()
    return {"servers": await servers.overview(), "chat": cfg["chat"], "deep": cfg["deep"]}


@admin_routes.post("/api/brains/servers/test")
async def servers_test(request: Request, _: str = Depends(require_admin)):
    body = await request.json()
    return await servers.test(str(body.get("flavor", "ollama")), str(body.get("url", "")), str(body.get("key", "")).strip())


@admin_routes.post("/api/brains/servers")
async def servers_add(request: Request, user: str = Depends(require_admin)):
    body = await request.json()
    name, flavor, key = str(body.get("name", "")).strip(), str(body.get("flavor", "ollama")), str(body.get("key", "")).strip()
    probe = await servers.test(flavor, str(body.get("url", "")), key)
    if not probe["ok"] and not body.get("force"):
        raise HTTPException(400, probe["error"])
    if not probe["ok"]:
        try:
            probe["root"], probe["base_url"] = servers.addresses(flavor, str(body.get("url", "")))
        except ValueError as exc:
            raise HTTPException(400, str(exc))
    try:
        pid = vault.add_server(name or probe["root"].split("//", 1)[-1], flavor, probe["root"], probe["base_url"], key)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    brains.invalidate()
    store.event("INFO", f"Server di modelli {probe['root']} aggiunto da {user}", "models")
    return {"id": pid, "models": probe.get("models", [])}


@admin_routes.delete("/api/brains/servers/{pid}")
async def servers_remove(pid: str, user: str = Depends(require_admin)):
    if not servers.known(pid):
        raise HTTPException(404, "Server sconosciuto")
    prefix = f"cloud:{pid}/"
    env = brains.config()
    updates = {}
    for kind, key in (("chat", "JARVIS_LLM_CHAT_ORDER"), ("deep", "JARVIS_LLM_DEEP_ORDER")):
        if env[f"{kind}_custom"]:
            kept = [m for m in env[kind] if not m.startswith(prefix)]
            if len(kept) != len(env[kind]):
                updates[key] = ",".join(kept)
    if updates:
        write_env(updates)
    vault.remove_server(pid)
    brains.invalidate()
    store.event("INFO", f"Server di modelli {pid} rimosso da {user}", "models")
    return {"ok": True}
