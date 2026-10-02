from fastapi import APIRouter, Depends, HTTPException, Request

from access import require_admin
from config import DEMO
from core_client import core
from features.chat import voice_id
from features.people import people
from features.vision.proxy import vision_proxy
from features.voices.catalog import VOICES
from state import store
from tasks import background

admin_routes = APIRouter()


async def sync_person_neuron(slug: str) -> None:
    p = people.get(slug)
    if not p:
        return
    props = {"role": p.get("role"), "preferences": p.get("preferences", {}),
             "habits": p["habits"]["summary"], "visits": p.get("stats", {}).get("visits", 0)}
    await core.remember(("node", {"id": f"person:{slug}", "node_type": "USER", "label": p["name"], "properties": props}))


@admin_routes.get("/api/people")
async def admin_people_list(_: str = Depends(require_admin)):
    return {"people": people.all_profiles(), "roles": people.ROLES, "voices": VOICES}


@admin_routes.get("/api/people/schema")
async def admin_people_schema(_: str = Depends(require_admin)):
    return {**people.schema(), "voices": VOICES}


@admin_routes.get("/api/people/reminders")
async def admin_reminders(days: int = 30, _: str = Depends(require_admin)):
    return {"reminders": people.reminders(max(1, min(days, 366)))}


@admin_routes.get("/api/people/{slug}")
async def admin_person(slug: str, _: str = Depends(require_admin)):
    p = people.get(slug)
    if not p:
        raise HTTPException(404, "Persona non trovata")
    p["sessions"] = p.get("sessions", [])[-50:]
    p["voiceprint"] = voice_id.status(slug)
    return p


@admin_routes.post("/api/people")
async def admin_person_create(request: Request, user: str = Depends(require_admin)):
    name = str((await request.json()).get("name", "")).strip()
    if not name or len(name) > 40:
        raise HTTPException(400, "Nome non valido")
    p = people.ensure(people.slugify(name), name)
    background(sync_person_neuron(p["slug"]))
    store.event("INFO", f"Profilo creato: {name} (da {user})", "people")
    return p


@admin_routes.put("/api/people/{slug}")
async def admin_person_update(slug: str, request: Request, _: str = Depends(require_admin)):
    changes = await request.json()
    try:
        p = people.update(slug, changes)
        if changes.get("name") and not DEMO:
            await vision_proxy(f"/people/{slug}", "PATCH", {"name": p["name"]})
    except KeyError:
        raise HTTPException(404, "Persona non trovata")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    background(sync_person_neuron(slug))
    return {"ok": True, "updated_at": p["updated_at"]}


@admin_routes.delete("/api/people/{slug}/voiceprint")
async def admin_person_voiceprint_delete(slug: str, user: str = Depends(require_admin)):
    if not people.load(slug):
        raise HTTPException(404, "Persona non trovata")
    voice_id.forget(slug)
    store.event("INFO", f"Impronta vocale cancellata: {slug} (da {user})", "people")
    return {"ok": True, "voiceprint": voice_id.status(slug)}


@admin_routes.delete("/api/people/{slug}")
async def admin_person_delete(slug: str, user: str = Depends(require_admin)):
    people.delete(slug)
    if not DEMO:
        await vision_proxy(f"/people/{slug}", "DELETE")
    store.event("INFO", f"Persona eliminata con tutti i dati: {slug} (da {user})", "people")
    return {"ok": True}
