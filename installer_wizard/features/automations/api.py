import copy

from fastapi import APIRouter, Depends, HTTPException, Request

from access import require_admin
from features.automations import builder, sun, templates
from features.automations.bus import bus
from features.automations.engine import enabled, engine
from features.automations.expr import ExprError, evaluate
from features.automations.library import InvalidAutomation, library
from features.automations.schema import catalog, validate

public_routes = APIRouter()
admin_routes = APIRouter()


def _find(aid: str) -> dict:
    try:
        return library.get(aid)
    except KeyError:
        raise HTTPException(404, "Automazione sconosciuta")


def _bad(exc: InvalidAutomation):
    raise HTTPException(422, {"message": "L'automazione non è valida", "errors": exc.errors})


@admin_routes.get("/api/automations")
async def overview(_: str = Depends(require_admin)):
    active = [r.view() for r in engine.active.values()]
    return {"enabled": enabled(), "status": engine.status, "rev": engine.rev + library.rev,
            "automations": library.all(), "active": active, "recent": [{k: v for k, v in r.items() if k != "trace"} for r in engine.recent[:30]],
            "waiting": [{"run": r.id, "name": r.name} for r, _ in engine.runner.asking]}


@admin_routes.get("/api/automations/catalog")
async def schema(_: str = Depends(require_admin)):
    from features.desktop.desk import desk
    try:
        from features.sounds.library import sounds
        sound_names = sounds.names()
    except Exception:
        sound_names = []
    t = sun.times()
    return {**catalog(), "entities": bus.states.catalog(), "widgets": sorted(desk.widgets.keys()),
            "sounds": sound_names, "templates": templates.listing(),
            "automations": [{"id": a["id"], "name": a["name"]} for a in library.all()],
            "sun": {k: v.strftime("%H:%M") if v else "" for k, v in t.items()}, "place": sun.PLACE["name"],
            "globals": bus.states.globals, "events_recent": bus.recent[-30:]}


@admin_routes.post("/api/automations")
async def create(request: Request, user: str = Depends(require_admin)):
    try:
        return library.add(await request.json(), origin=f"pannello ({user})")
    except InvalidAutomation as exc:
        _bad(exc)


@admin_routes.post("/api/automations/validate")
async def check(request: Request, _: str = Depends(require_admin)):
    spec, errors = validate(await request.json())
    return {"ok": not errors, "errors": errors, "automation": spec}


@admin_routes.post("/api/automations/generate")
async def generate(request: Request, _: str = Depends(require_admin)):
    body = await request.json()
    text = str(body.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "Descriva l'automazione che desidera")
    current = library.items.get(str(body.get("id") or ""))
    try:
        spec, errors = await builder.build(text, current)
    except Exception as exc:
        raise HTTPException(503, f"Nessun cervello disponibile per progettare l'automazione: {exc}")
    return {"automation": spec, "errors": errors}


@admin_routes.post("/api/automations/expr")
async def test_expr(request: Request, _: str = Depends(require_admin)):
    body = await request.json()
    try:
        value = evaluate(str(body.get("expr") or ""), engine.runner.names({"vars": body.get("vars") or {}}))
        return {"ok": True, "value": value if isinstance(value, (int, float, bool, str, list, dict)) or value is None else str(value)}
    except (ExprError, TypeError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


@admin_routes.get("/api/automations/runs")
async def runs(automation: str = "", limit: int = 80, _: str = Depends(require_admin)):
    return {"runs": [{k: v for k, v in r.items() if k != "trace"} for r in library.history(min(400, limit), automation)]}


@admin_routes.get("/api/automations/runs/{rid}")
async def run_detail(rid: str, _: str = Depends(require_admin)):
    live = engine.active.get(rid)
    if live:
        return live.view(full=True)
    found = next((r for r in engine.recent if r["id"] == rid), None) or library.find_run(rid)
    if not found:
        raise HTTPException(404, "Esecuzione non trovata")
    return found


@admin_routes.post("/api/automations/runs/{rid}/stop")
async def stop_run(rid: str, _: str = Depends(require_admin)):
    return {"ok": engine.stop(rid)}


@admin_routes.post("/api/automations/templates/{index}")
async def from_template(index: int, user: str = Depends(require_admin)):
    if not 0 <= index < len(templates.TEMPLATES):
        raise HTTPException(404, "Modello sconosciuto")
    spec = copy.deepcopy(templates.TEMPLATES[index])
    spec["enabled"] = False
    try:
        return library.add(spec, origin=f"modello ({user})")
    except InvalidAutomation as exc:
        _bad(exc)


@admin_routes.get("/api/automations/export")
async def export(_: str = Depends(require_admin)):
    return {"version": 1, "automations": library.all(), "globals": bus.states.globals}


@admin_routes.post("/api/automations/import")
async def import_(request: Request, user: str = Depends(require_admin)):
    body = await request.json()
    items = body.get("automations") if isinstance(body, dict) else body
    done, failed = [], []
    for spec in items or []:
        try:
            done.append(library.add({**spec, "enabled": False}, origin=f"importata ({user})")["name"])
        except InvalidAutomation as exc:
            failed.append({"name": (spec or {}).get("name"), "errors": exc.errors})
    return {"imported": done, "failed": failed}


@admin_routes.get("/api/automations/{aid}")
async def detail(aid: str, _: str = Depends(require_admin)):
    return _find(aid)


@admin_routes.put("/api/automations/{aid}")
async def update(aid: str, request: Request, _: str = Depends(require_admin)):
    a = _find(aid)
    try:
        return library.update(a["id"], await request.json())
    except InvalidAutomation as exc:
        _bad(exc)


@admin_routes.delete("/api/automations/{aid}")
async def delete(aid: str, _: str = Depends(require_admin)):
    library.remove(_find(aid)["id"])
    return {"ok": True}


@admin_routes.post("/api/automations/{aid}/run")
async def run_now(aid: str, request: Request, _: str = Depends(require_admin)):
    a = _find(aid)
    body = await request.json() if (request.headers.get("content-length") or "0") != "0" else {}
    run = engine.start(a, {"type": "manual", "label": "avviata dal pannello", "data": body.get("data") or {}},
                       check=bool(body.get("check")), force=True)
    if not run:
        return {"ok": False, "message": "Non avviata: condizioni non soddisfatte o già in corso"}
    return {"ok": True, "run": run.id}


@admin_routes.post("/api/automations/{aid}/toggle")
async def toggle(aid: str, request: Request, _: str = Depends(require_admin)):
    a = _find(aid)
    body = await request.json()
    return {"ok": True, "message": engine.set_enabled(a["id"], bool(body.get("enabled")))}


@admin_routes.post("/api/automations/{aid}/duplicate")
async def duplicate(aid: str, _: str = Depends(require_admin)):
    return library.duplicate(_find(aid)["id"])


@public_routes.post("/api/automations/webhook/{key}")
async def webhook(key: str, request: Request):
    if len(key) < 16:
        raise HTTPException(404, "Sconosciuto")
    try:
        data = await request.json()
    except ValueError:
        data = {"text": (await request.body()).decode("utf-8", "replace")[:4000]}
    started = engine.webhook(key, data if isinstance(data, dict) else {"value": data})
    if not started:
        raise HTTPException(404, "Nessuna automazione per questa chiave")
    return {"ok": True, "started": started}
