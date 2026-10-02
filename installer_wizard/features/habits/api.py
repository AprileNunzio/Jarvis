from fastapi import APIRouter, Depends, HTTPException, Request

from access import require_admin
from features.habits.service import enabled, habits, threshold

public_routes = APIRouter()
admin_routes = APIRouter()


@admin_routes.get("/api/habits")
async def overview(_: str = Depends(require_admin)):
    items = sorted(habits.data["suggestions"].values(), key=lambda s: (s["status"] != "new", -s["confidence"]))
    return {"enabled": enabled(), "threshold": threshold(), "events": habits.journal.count(), "mined": habits.data.get("mined", 0),
            "asking": habits.waiting(), "suggestions": items, "anomalies": habits.data.get("anomalies", [])[:20]}


@admin_routes.post("/api/habits/analyse")
async def analyse(_: str = Depends(require_admin)):
    import asyncio
    found = await asyncio.to_thread(habits.analyse)
    return {"found": len(found)}


@admin_routes.post("/api/habits/{sid}")
async def decide(sid: str, request: Request, _: str = Depends(require_admin)):
    body = await request.json()
    verdict = str(body.get("verdict") or "")
    if verdict not in ("accept", "reject", "snooze"):
        raise HTTPException(400, "Decisione non valida")
    if sid not in habits.data["suggestions"]:
        raise HTTPException(404, "Proposta sconosciuta")
    return {"message": habits.decide(sid, verdict)}
