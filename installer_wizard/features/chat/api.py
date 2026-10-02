import asyncio
import json
import random
import re
import time

import httpx
from access import NO_CACHE, is_local, lang_of, require_admin, require_display
from config import DEMO
from core_client import core
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from state import store
from tasks import background

from features.brain.brains import brains
from features.brain.residency import primary
from features.chat import addressee, assistant, brain_chain, intents, speaker, voice_id, wake
from features.chat.dialogue import dialogue
from features.chat.layout import presence
from features.chat.skills import ambient
from features.laws import guard
from features.laws.laws import laws
from features.mind.mind import mind
from features.chat import context as request_context
from features.desktop.desk import desk
from features.people import people
from features.skills.library import library as skill_library
from features.study import study
from features.voices import languages
from features.voices.catalog import home_lang
from features.voices.downloads import ensure_language

public_routes = APIRouter()
admin_routes = APIRouter()

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
DEMO_LONG = ("Ecco una panoramica dettagliata della tua richiesta. Ho analizzato le informazioni disponibili "
             "e le ho organizzate per te.\n- Primo punto importante da considerare\n"
             "- Secondo aspetto, con qualche dettaglio in più\n- Terzo elemento conclusivo\n"
             "Fammi sapere se vuoi approfondire.")


async def _demo_core(query: str) -> dict:
    await asyncio.sleep(1.2)
    if len(query) > 30:
        return {"agent_id": "demo", "speech_output": DEMO_LONG}
    return {"agent_id": "demo", "speech_output": f"Modalità dimostrativa: ho ricevuto «{query}»."}


async def _core_call(query: str, device: str, speech_lang: dict) -> dict:
    present = [p["slug"] for p in store.presence.get("people", []) if p.get("known")]
    context = {"people_present": people.context_for(present)} if present else {}
    context["laws"] = laws.preamble()
    context["speaker"] = speaker.instruction()
    recent = dialogue.context(device)
    if recent:
        context["dialogue"] = recent
    knowledge = await study.engine.recall(query)
    if knowledge:
        context["knowledge"] = knowledge
    long_term = mind.recall(query, who=request_context.voice.get())
    if long_term:
        context["long_term"] = long_term
    route = await brains.route(query)
    rule = languages.instruction(speech_lang["lang"], speech_lang["teach"])
    if rule:
        context["reply_language"] = rule

    async def core_local(models: list[str]) -> dict:
        payload = {"query": query, "device_id": device,
                   "context": {**context, "models": models, "max_tokens": route["max_tokens"],
                               "pinned": primary() or ""}}
        started = time.time()
        r = await core.request("POST", "/api/v1/command", json=payload, timeout=240)
        r.raise_for_status()
        data = r.json()
        model = ((data.get("result_data") or {}).get("model") or "").removeprefix("ollama/")
        if model:
            brains.record(model, (time.time() - started) * 1000, model in models, route["kind"])
            label = "veloce" if route["kind"] == "chat" else "ragionamento"
            data["agent_id"] = f"{data.get('agent_id') or 'core'} · {model} ({label})"
        return data

    try:
        return await brain_chain.ask(query, device, context, route, core_local)
    except brain_chain.NoBrainAvailable as exc:
        store.event("ERROR", f"Nessun cervello ha risposto: {exc}", "core")
        raise HTTPException(502, "Nessun cervello disponibile: controlla modelli locali e chiavi cloud")


def _heard(body: dict) -> dict:
    slug = str(body.get("speaker") or "")
    known = body.get("voice_known")
    return {"followup": bool(body.get("followup")), "speaker": slug if SLUG_RE.match(slug) else "",
            "voice_known": known if isinstance(known, bool) else None}


async def assistant_chat(text: str, device: str, heard_lang: str | None = None, heard: dict | None = None) -> JSONResponse:
    heard = heard or {}
    text = (text or "").strip()
    if not text:
        raise HTTPException(400, "Messaggio vuoto")
    if len(text) > 4000:
        raise HTTPException(413, "Messaggio troppo lungo")
    if store.phase not in ("READY", "DEGRADED"):
        raise HTTPException(503, "Jarvis non è ancora operativo")
    study.engine.activity("chat")
    request_context.device.set(device)
    request_context.voice.set(heard.get("speaker") or "")
    directed, confidence = True, 1.0
    if heard.get("followup"):
        verdict = addressee.judge(text, device)
        directed, confidence = verdict.directed, verdict.score
        if not verdict.directed:
            return JSONResponse({"ignored": True, "reason": verdict.reason, "score": verdict.score})
    said, text = text, dialogue.resolve(device, text)
    speech_lang = languages.resolve(text, device, heard_lang)
    if speech_lang["lang"] != home_lang():
        background(ensure_language(speech_lang["lang"]))

    async def core_call(query: str) -> dict:
        return await (_demo_core(query) if DEMO else _core_call(query, device, speech_lang))

    enroll = voice_id.command(text)
    if guard.attempt(said) or guard.attempt(text):
        guard.record(said, device)
        result = {"reply": guard.REFUSAL, "intent": "laws", "agent": "leggi fondamentali", "elapsed_ms": 0}
    elif enroll:
        result = {"reply": enroll[0], "ui": enroll[1], "intent": "voice_id", "agent": "impronta vocale", "elapsed_ms": 0}
    else:
        result = await assistant.handle(text, core_call, speech_lang)
    result["reply"] = speaker.fix_address(result.get("reply") or "") + voice_id.offer(heard.get("voice_known"))
    if isinstance(result.get("ui"), dict):
        result["ui"].setdefault("presence", presence(result["reply"], result["ui"]))
    dialogue.remember(device, said, result["reply"], result.get("intent", ""))
    result["lang"] = languages.detect(result.get("reply") or "", speech_lang["lang"])
    result["language"] = {**speech_lang, "label": languages.label(speech_lang["lang"])}
    study.engine.note_query(text, result.get("intent", ""))
    desk.on_intent(result.get("intent", ""), result.get("ui") or {})
    if not str(result.get("agent", "")).startswith("algoritmo") and skill_library.needs_algorithm(text):
        background(skill_library.learn(text, brains.config()["deep"]))
    background(mind.evaluate(said, result.get("reply", ""), result.get("intent", ""), device, directed, confidence,
                             (result.get("ui") or {}).get("mode", ""), str(result.get("agent", "")),
                             heard.get("speaker") or ""))
    return JSONResponse(result)


async def assistant_reply(text: str, device: str, lang: str | None = None) -> dict:
    return json.loads((await assistant_chat(text, device, lang)).body)


def _demo_graph() -> dict:
    rnd = random.Random(7)
    types = ["CONCEPT"] * 5 + ["MEMORY"] * 3 + ["AGENT", "SKILL", "SKILL", "DEVICE", "LOCATION", "USER"]
    count = 70 + int(time.time() // 20) % 5
    nodes = [{"id": f"n{i}", "node_type": rnd.choice(types), "label": f"Ricordo {i}",
              "properties": {"demo": True}, "created_at": time.time() - i * 600} for i in range(count)]
    edges = [{"source_id": f"n{rnd.randrange(count)}", "target_id": f"n{rnd.randrange(count)}",
              "relation_type": "CONNECTED_TO", "weight": 1.0} for _ in range(count)]
    return {"nodes": nodes, "edges": [e for e in edges if e["source_id"] != e["target_id"]]}


@public_routes.post("/api/assistant/chat")
async def public_chat(request: Request):
    require_display(request, "Per parlare con Jarvis da remoto accedi al pannello :8080")
    body = await request.json()
    return await assistant_chat(body.get("text", ""), "kiosk" if is_local(request) else "remote", lang_of(body),
                                _heard(body))


@public_routes.get("/api/ambient")
async def public_ambient():
    return await ambient.current()


@public_routes.post("/api/assistant/wake")
async def public_wake(request: Request):
    require_display(request)
    request_context.device.set("kiosk" if is_local(request) else "remote")
    from features.automations.bus import emit
    emit("wake", {"device": request_context.device.get()})
    result = await wake.greeting()
    desk.show("g_notify", result["card"], key="wake", ttl=25)
    dialogue.remember(request_context.device.get(), "Jarvis", result["reply"], "wake")
    return result


@admin_routes.post("/api/assistant/chat")
async def admin_chat(request: Request, _: str = Depends(require_admin)):
    body = await request.json()
    return await assistant_chat(body.get("text", ""), "admin", lang_of(body))


@public_routes.post("/api/activity")
async def public_activity(request: Request):
    require_display(request)
    study.engine.activity("display")
    return {"ok": True}


@public_routes.get("/api/assistant/predict")
async def public_predict(q: str = ""):
    return intents.predict(q[:500])


@public_routes.get("/api/assistant/memory")
async def public_memory():
    if DEMO:
        return _demo_graph()
    try:
        r = await core.request("GET", "/api/v1/knowledge/graph", timeout=20)
        return JSONResponse(r.json().get("graph", {}), headers=NO_CACHE)
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, "Memoria non disponibile")
