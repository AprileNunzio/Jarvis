from fastapi import APIRouter, Depends, HTTPException, Request

from access import require_admin
from features.autonomy import approvals, journal
from features.autonomy.engine import autonomy, enabled
from features.autonomy.routines import describe, parse_when, routines
from tasks import background

public_routes = APIRouter()
admin_routes = APIRouter()


def _view(r: dict) -> dict:
    return {**r, "when_text": describe(r.get("when") or {})}


@admin_routes.get("/api/autonomy")
async def overview(_: str = Depends(require_admin)):
    return {"enabled": enabled(), "status": autonomy.status, "last_autopilot": autonomy.last_autopilot,
            "routines": [_view(r) for r in routines.all()],
            "approvals": [{k: v for k, v in a.items() if k != "steps"} for a in approvals.pending()],
            "journal": journal.recent(80)}


@admin_routes.post("/api/autonomy/routines")
async def add_routine(request: Request, user: str = Depends(require_admin)):
    body = await request.json()
    prompt, when = str(body.get("prompt") or "").strip(), str(body.get("when") or "").strip()
    if not prompt or not when:
        raise HTTPException(400, "Servono «quando» e «cosa fare»")
    item = routines.add(str(body.get("title") or prompt[:60]), prompt, parse_when(when), origin=f"pannello ({user})")
    return _view(item)


@admin_routes.put("/api/autonomy/routines/{rid}")
async def edit_routine(rid: str, request: Request, _: str = Depends(require_admin)):
    body, changes = await request.json(), {}
    if "enabled" in body:
        changes["enabled"] = bool(body["enabled"])
    if "trusted" in body:
        changes["trusted"] = bool(body["trusted"])
    if body.get("title"):
        changes["title"] = str(body["title"])[:80]
    if body.get("prompt"):
        changes["prompt"] = str(body["prompt"])[:1000]
    if body.get("when"):
        changes["when"] = parse_when(str(body["when"]))
    try:
        return _view(routines.update(rid, **changes))
    except KeyError:
        raise HTTPException(404, "Compito sconosciuto")


@admin_routes.delete("/api/autonomy/routines/{rid}")
async def delete_routine(rid: str, _: str = Depends(require_admin)):
    routines.remove(rid)
    return {"ok": True}


@admin_routes.post("/api/autonomy/routines/{rid}/run")
async def run_routine(rid: str, _: str = Depends(require_admin)):
    try:
        item = routines.get(rid)
    except KeyError:
        raise HTTPException(404, "Compito sconosciuto")
    background(autonomy.run_routine(item, "avviato dal pannello"))
    return {"ok": True}


@admin_routes.post("/api/autonomy/approvals/{aid}")
async def decide(aid: str, request: Request, _: str = Depends(require_admin)):
    body = await request.json()
    try:
        result = await autonomy.approve(aid, bool(body.get("approve")), bool(body.get("always")))
    except KeyError:
        raise HTTPException(404, "Richiesta già gestita o scaduta")
    return {"ok": True, "result": result}


@admin_routes.post("/api/autonomy/autopilot")
async def autopilot_now(_: str = Depends(require_admin)):
    background(autonomy.autopilot())
    return {"ok": True}
