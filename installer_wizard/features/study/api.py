import json

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse

from access import require_admin
from core_client import core
from feature_registry import registry
from features.soup.api import trainer
from features.study import study
from state import store

admin_routes = APIRouter()
engine = study.engine


async def _study_neuron(topic: dict, lesson: dict | None, overview: dict) -> None:
    topic_id = f"study:topic:{topic['id']}"
    items = [("node", {"id": topic_id, "node_type": "CONCEPT", "label": f"Studio: {topic['name']}",
                       "properties": {"livello": overview["level_name"],
                                      "avanzamento": f"{overview['progress'] * 100:.0f}%",
                                      "celle": overview["cells"], "origine": topic["source"]}})]
    if lesson:
        lesson_id = f"study:lesson:{lesson['id']}"
        items += [("node", {"id": lesson_id, "node_type": "MEMORY", "label": lesson["title"],
                            "properties": {"materia": topic["name"], "livello": overview["level_name"],
                                           "sintesi": (lesson.get("summary") or "")[:300],
                                           "fonti": [x["url"] for x in lesson.get("sources", [])]}}),
                  ("edge", {"source_id": lesson_id, "target_id": topic_id, "relation_type": "DEPENDS_ON",
                            "weight": 1.0})]
    await core.remember(*items)


engine.on_neuron = _study_neuron
registry.register_hook("study", lambda: bool(engine.settings.get("enabled")),
                       lambda on: engine.update_settings({"enabled": bool(on)}))


@admin_routes.get("/api/study")
async def admin_study(_: str = Depends(require_admin)):
    return {**engine.summary(), "soup": trainer.summary()}


@admin_routes.put("/api/study/settings")
async def admin_study_settings(request: Request, _: str = Depends(require_admin)):
    body = await request.json()
    try:
        result = engine.update_settings(body)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if "enabled" in body:
        registry.note_hook_change("study", bool(body["enabled"]))
    return result


@admin_routes.post("/api/study/topics")
async def admin_study_add(request: Request, user: str = Depends(require_admin)):
    body = await request.json()
    try:
        t = engine.add_topic(str(body.get("name", "")), "manual", int(body.get("target_level", 4)),
                             int(body.get("priority", 3)), str(body.get("focus", "")))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    store.event("INFO", f"Studio: materia «{t['name']}» aggiunta da {user}", "study")
    return engine.overview(t)


@admin_routes.get("/api/study/topics/{tid}")
async def admin_study_topic(tid: str, _: str = Depends(require_admin)):
    try:
        return engine.topic_detail(tid)
    except KeyError:
        raise HTTPException(404, "Materia sconosciuta")


@admin_routes.put("/api/study/topics/{tid}")
async def admin_study_topic_update(tid: str, request: Request, _: str = Depends(require_admin)):
    try:
        return engine.overview(engine.update_topic(tid, await request.json()))
    except KeyError:
        raise HTTPException(404, "Materia sconosciuta")
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@admin_routes.delete("/api/study/topics/{tid}")
async def admin_study_topic_delete(tid: str, user: str = Depends(require_admin)):
    engine.delete_topic(tid)
    store.event("INFO", f"Studio: materia {tid} eliminata da {user}", "study")
    return {"ok": True}


@admin_routes.post("/api/study/topics/{tid}/reset")
async def admin_study_topic_reset(tid: str, _: str = Depends(require_admin)):
    try:
        return engine.overview(engine.reset_topic(tid))
    except KeyError:
        raise HTTPException(404, "Materia sconosciuta")


@admin_routes.post("/api/study/mentions/{key}")
async def admin_study_mention(key: str, _: str = Depends(require_admin)):
    m = engine.data["mentions"].pop(key, None)
    if not m:
        raise HTTPException(404, "Proposta non trovata")
    t = engine.add_topic(m["name"], "auto")
    t["hints"] = m.get("hints", [])
    engine.save()
    return engine.overview(t)


@admin_routes.delete("/api/study/mentions/{key}")
async def admin_study_mention_drop(key: str, _: str = Depends(require_admin)):
    engine.data["mentions"].pop(key, None)
    engine.save()
    return {"ok": True}


@admin_routes.post("/api/study/now")
async def admin_study_now(user: str = Depends(require_admin)):
    if not engine.settings.get("enabled"):
        raise HTTPException(409, "Attiva prima lo studio autonomo")
    engine.study_now(30)
    store.event("INFO", f"Studio avviato manualmente da {user} (30 minuti)", "study")
    return {"ok": True}


@admin_routes.post("/api/study/search")
async def admin_study_search(request: Request, _: str = Depends(require_admin)):
    q = str((await request.json()).get("q", "")).strip()[:300]
    if not q:
        raise HTTPException(400, "Domanda vuota")
    try:
        hits = await engine.recall_cells(q, 8, min_score=0.0)
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise HTTPException(502, f"Memoria non interrogabile: {exc}")
    return {"results": [{k: h.get(k) for k in ("text", "score", "topic_name", "level", "kind", "source", "strength")}
                        for h in hits], "timing": engine.memory.last_search}


@admin_routes.get("/api/study/dataset.jsonl")
async def admin_study_dataset(_: str = Depends(require_admin)):
    rows = engine.dataset()
    return PlainTextResponse("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                             media_type="application/jsonl",
                             headers={"Content-Disposition": 'attachment; filename="jarvis-studio.jsonl"'})
