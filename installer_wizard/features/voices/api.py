import asyncio
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from access import NO_CACHE, lang_of, require_admin, require_display
from config import write_env
from features.people import people
from features.study import study
from features.voices import catalog, downloads, languages, overview, synthesis
from state import store

public_routes = APIRouter()
admin_routes = APIRouter()
_VOICE_RE = re.compile(r"^[A-Za-z0-9_-]{2,60}$")


async def tts_response(text: str, lang: str | None = None) -> Response:
    study.engine.activity("voce")
    chosen_voice, chosen_speed, chosen_pitch, chosen_volume = None, None, None, None
    for p in store.presence.get("people", []):
        profile = people.load(p["slug"]) if p.get("known") else None
        if profile and profile.get("voice"):
            chosen_voice = profile["voice"].get("tts_voice") or None
            chosen_speed = float(profile["voice"].get("speed") or 0) or None
            chosen_pitch = profile["voice"].get("pitch")
            chosen_volume = profile["voice"].get("volume")
            break
    try:
        wav = await synthesis.synthesize(text, chosen_voice, chosen_speed, lang,
                                         pitch=float(chosen_pitch) if chosen_pitch not in (None, "") else None,
                                         volume=float(chosen_volume) if chosen_volume not in (None, "") else None)
    except ValueError:
        raise HTTPException(400, "Testo vuoto")
    except (RuntimeError, asyncio.TimeoutError) as exc:
        raise HTTPException(503, f"Voce neurale non disponibile: {exc}")
    return Response(wav, media_type="audio/wav", headers=NO_CACHE)


@public_routes.post("/api/assistant/tts")
async def public_tts(request: Request):
    require_display(request)
    body = await request.json()
    return await tts_response(str(body.get("text", "")), lang_of(body))


@admin_routes.post("/api/assistant/tts")
async def admin_tts(request: Request, _: str = Depends(require_admin)):
    body = await request.json()
    return await tts_response(str(body.get("text", "")), lang_of(body))


@admin_routes.get("/api/voices")
async def admin_voices(_: str = Depends(require_admin)):
    return await overview.overview()


@admin_routes.put("/api/voices")
async def admin_voices_set(request: Request, user: str = Depends(require_admin)):
    order = [str(v).strip() for v in (await request.json()).get("order", []) if str(v).strip()]
    if len(order) > 12 or not all(_VOICE_RE.match(v) for v in order):
        raise HTTPException(400, "Elenco di voci non valido")
    order = list(dict.fromkeys(order))
    write_env({"JARVIS_VOICE_ORDER": ",".join(order), **({"JARVIS_VOICE": order[0]} if order else {})})
    store.event("INFO", f"Ordine delle voci aggiornato da {user}: {', '.join(order) or 'automatico'}", "voice")
    return await overview.overview()


@admin_routes.post("/api/voices/download")
async def admin_voice_download(request: Request, _: str = Depends(require_admin)):
    name = str((await request.json()).get("voice", "")).strip()
    if not catalog.is_piper(name) or name not in catalog.piper_catalog():
        raise HTTPException(400, "Voce non valida")
    await downloads.start_download(name)
    return {"ok": True}


@admin_routes.put("/api/voices/language")
async def admin_voice_language(request: Request, user: str = Depends(require_admin)):
    body = await request.json()
    lang, name = languages.base(str(body.get("lang", ""))), str(body.get("voice", "")).strip()
    if lang not in languages.LANGS or (name and not _VOICE_RE.match(name)):
        raise HTTPException(400, "Lingua o voce non valida")
    prefs = catalog.lang_prefs()
    prefs.pop(lang, None)
    if name:
        prefs[lang] = name
        await downloads.start_download(name)
    write_env({"JARVIS_VOICE_LANG": catalog.lang_prefs_env(prefs)})
    store.event("INFO", f"Voce per {languages.label(lang).lower()} impostata da {user}: {name or 'automatica'}", "voice")
    return await overview.overview()


@admin_routes.post("/api/voices/ensure")
async def admin_voice_ensure(request: Request, _: str = Depends(require_admin)):
    lang = languages.base(str((await request.json()).get("lang", "")))
    if lang not in languages.LANGS:
        raise HTTPException(400, "Lingua non valida")
    return await downloads.ensure_language(lang)


@admin_routes.delete("/api/voices/{name}")
async def admin_voice_delete(name: str, _: str = Depends(require_admin)):
    if not catalog.is_piper(name):
        raise HTTPException(400, "Solo le voci Piper scaricate possono essere eliminate")
    if name in catalog.custom_order():
        raise HTTPException(409, "La voce è nell'elenco di priorità: toglila prima dall'elenco")
    try:
        downloads.delete_piper(name)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return await overview.overview()


@admin_routes.post("/api/voices/preview")
async def admin_voice_preview(request: Request, _: str = Depends(require_admin)):
    body = await request.json()
    name = str(body.get("voice", ""))
    if not _VOICE_RE.match(name):
        raise HTTPException(400, "Voce non valida")
    lang = catalog.describe(name)["lang"]
    text = synthesis.normalize(str(body.get("text") or catalog.SAMPLES.get(lang, catalog.SAMPLES["it"])), lang)[:300]
    if catalog.is_piper(name) and not catalog.piper_installed(name):
        raise HTTPException(409, "Voce non ancora scaricata")
    try:
        wav = await synthesis.speak_with(text, name, 1.0)
    except (httpx.HTTPError, RuntimeError, OSError) as exc:
        raise HTTPException(503, f"Voce non disponibile: {exc}")
    return Response(wav, media_type="audio/wav", headers=NO_CACHE)
