from access import require_admin, require_display
from fastapi import APIRouter, Depends, HTTPException, Request

from features.brain.assignments import AssignmentError, parse_assignment
from features.brain.brains import brains, norm
from features.brain.components import BY_ID as COMPONENTS
from features.brain.keepalive import CHOICES, keep_alive_policy
from features.brain.residency import apply
from features.brain.roles import ROLES
from features.brain.routing import assignment_service
from features.brain.trace import trace
from features.cloud import servers
from features.cloud.catalog import PROVIDERS, is_server
from features.cloud.vault import vault
from state import store
from tasks import background

admin_routes = APIRouter()
public_routes = APIRouter()


async def _pool(installed: set[str]) -> list[dict]:
    refs = [name for name in await brains.installed() if "embed" not in name]
    for row in await servers.overview():
        refs += [f"cloud:{row['id']}/{model}" for model in row["models"]]
    for provider in PROVIDERS:
        if vault.configured(provider.id) and not is_server(provider.id):
            refs += [f"cloud:{provider.id}/{model}" for model in provider.models]
    return [{**brains.describe(ref), "available": brains.usable(ref, installed)} for ref in dict.fromkeys(refs)]


@admin_routes.get("/api/brains/assignments")
async def assignments_overview(_: str = Depends(require_admin)):
    installed = {norm(n) for n in await brains.installed()}
    return {"components": assignment_service.overview(installed),
            "roles": [{"id": r.id, "icon": r.icon, "label": r.label} for r in ROLES],
            "pool": await _pool(installed)}


@admin_routes.put("/api/brains/assignments")
async def assignments_save(request: Request, user: str = Depends(require_admin)):
    body = await request.json()
    raw = body.get("updates")
    if not isinstance(raw, dict) or not raw:
        raise HTTPException(400, "Nessuna modifica")
    updates = {}
    for component_id, value in raw.items():
        if component_id not in COMPONENTS:
            raise HTTPException(400, f"Componente sconosciuto: {component_id}")
        try:
            updates[component_id] = None if value is None else parse_assignment(value)
        except AssignmentError as exc:
            raise HTTPException(400, f"Assegnazione non valida per {component_id}: {exc}")
    assignment_service.save(updates)
    store.event("INFO", f"Assegnazioni dei cervelli aggiornate da {user}: {', '.join(sorted(updates))}", "models")
    installed = {norm(n) for n in await brains.installed()}
    return {"components": assignment_service.overview(installed)}


@admin_routes.get("/api/brains/keepalive")
async def keepalive_overview(_: str = Depends(require_admin)):
    return {"choices": list(CHOICES), "overrides": keep_alive_policy.overrides()}


@admin_routes.put("/api/brains/keepalive")
async def keepalive_save(request: Request, user: str = Depends(require_admin)):
    changes = (await request.json()).get("changes")
    if not isinstance(changes, dict) or not changes:
        raise HTTPException(400, "Nessuna modifica")
    try:
        overrides = keep_alive_policy.set_many(changes)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    assignment_service.publish()
    for ref, value in changes.items():
        if value:
            background(apply(ref))
    store.event("INFO", f"Permanenza in memoria aggiornata da {user}: {', '.join(sorted(changes))}", "models")
    return {"choices": list(CHOICES), "overrides": overrides}


@public_routes.get("/api/brain/trace")
async def brain_trace(request: Request):
    require_display(request)
    return trace.snapshot()
