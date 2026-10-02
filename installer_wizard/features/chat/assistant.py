import importlib
import time

import httpx
from state import store

from features.actions import router as actions
from features.brain.llm import BrainUnavailable
from features.chat import code
from features.chat.compose import compose_generic
from features.chat.intents import detect_intent
from features.chat.skills.music import music_skill
from features.chat.skills.network import network_skill
from features.chat.skills.people import introduce_skill, vision_skill
from features.chat.skills.place import place_skill
from features.chat.skills.system import system_skill, time_skill
from features.chat.skills.voices import voices_skill
from features.chat.skills.weather import weather_skill
from features.chat.templates import remember_template

CONNECTORS = {"vault": "features.vault.commands", "selftest": "features.selftest.commands", "sounds": "features.sounds.commands", "screens": "features.desktop.commands", "models3d": "features.models3d.commands", "vision": "features.vision.sight", "gservices": "features.google.commands", "maps": "features.maps.maps"}


async def _agent(text: str, started: float) -> dict:
    from features.agent import commands as agent_cmd
    speech, ui = await agent_cmd.answer(text)
    return {"reply": speech, "ui": ui, "intent": "agent", "agent": "agente · strumenti",
            "elapsed_ms": int((time.time() - started) * 1000)}


async def handle(text: str, core_call, speech_lang: dict | None = None) -> dict:
    started = time.time()
    from features.automations.bus import emit
    emit("voice_command", {"text": text})
    try:
        from features.automations import commands as automation_cmd
        speech, ui = await automation_cmd.answer(text)
        return {"reply": speech, "ui": ui, "intent": "automations", "agent": "automazioni",
                "elapsed_ms": int((time.time() - started) * 1000)}
    except LookupError:
        pass
    from features.agent import commands as agent_cmd
    if agent_cmd.strong(text):
        return await _agent(text, started)
    try:
        from features.home_assistant.home import brain as home_brain
        home_out = await home_brain.handle(text)
    except Exception as exc:
        store.event("WARN", f"Casa non disponibile: {exc}", "home")
        home_out = None
    if home_out:
        speech, ui, agent = home_out
        elapsed = int((time.time() - started) * 1000)
        if ui.get("mode") != "face":
            remember_template("home", ui, elapsed)
        return {"reply": speech, "ui": ui, "intent": "home", "agent": agent, "elapsed_ms": elapsed}
    lang = (speech_lang or {}).get("lang", "it")
    if lang == "it" or actions.match(text):
        act = await actions.handle(text)
        if act:
            speech, ui, agent = act
            elapsed = int((time.time() - started) * 1000)
            return {"reply": speech, "ui": ui, "intent": "action", "agent": agent, "elapsed_ms": elapsed}
    if lang == "it":
        for connector, module in CONNECTORS.items():
            try:
                speech, ui = await importlib.import_module(module).answer(text)
            except LookupError:
                continue
            except Exception as exc:
                if type(exc).__name__ == "NotLinked":
                    speech, ui = str(exc), {"mode": "face"}
                else:
                    store.event("WARN", f"Connettore {connector}: {exc}", connector)
                    speech, ui = f"Non riesco a raggiungere il servizio in questo momento: {exc}", {"mode": "face"}
            elapsed = int((time.time() - started) * 1000)
            if ui.get("mode") != "face":
                remember_template(connector, ui, elapsed)
            return {"reply": speech, "ui": ui, "intent": connector, "agent": connector, "elapsed_ms": elapsed}
    intent = detect_intent(text)
    if (lang != "it" or (speech_lang or {}).get("switched")) and intent not in ("voices",):
        intent = "conversation"
    agent = "jarvis_ui"
    try:
        if intent == "weather":
            speech, ui = await weather_skill(text)
        elif intent == "system":
            speech, ui = system_skill()
        elif intent == "vision":
            speech, ui = vision_skill()
        elif intent == "network":
            speech, ui = await network_skill()
        elif intent == "introduce":
            speech, ui = await introduce_skill(text)
        elif intent == "time":
            speech, ui = time_skill()
        elif intent == "voices":
            speech, ui = await voices_skill(text)
        elif intent == "place":
            speech, ui = await place_skill(text)
        elif intent == "music":
            speech, ui = music_skill()
        elif intent == "study":
            from features.study.study import speech_summary
            speech, ui = speech_summary()
        elif intent == "brain":
            speech, ui = ("Ecco la mia mente. Ogni punto luminoso è un ricordo reale: "
                          "tocca un neurone per esplorarlo.", {"mode": "brain"})
        else:
            raise LookupError
    except LookupError:
        from features.skills.library import library
        solved = await library.try_answer(text)
        if solved:
            agent = f"algoritmo · {solved['name']} ({solved['total_ms']} ms)"
            speech, ui = solved["speech"], {"mode": "face"}
        elif actions.CALC.search(text) and (calc := await actions.try_calc(text)):
            agent = "calcolo verificato"
            speech, ui = calc
        else:
            agent, speech, ui = await _converse(text, core_call)
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        store.event("WARN", f"Abilità '{intent}' non disponibile: {exc}", "assistant")
        data = await core_call(text)
        agent = data.get("agent_id") or "core"
        speech, ui = code.answer(data.get("speech_output") or "", text) or compose_generic(data.get("speech_output") or "…", text)
    if ui.get("code"):
        intent = "code_view"

    elapsed = int((time.time() - started) * 1000)
    if ui.get("mode") != "face":
        remember_template(intent, ui, elapsed)
    return {"reply": speech, "ui": ui, "intent": intent, "agent": agent, "elapsed_ms": elapsed}


async def _diagnose(text: str) -> tuple[str, dict] | None:
    try:
        return await actions.diagnose_action(text)
    except BrainUnavailable as exc:
        store.event("WARN", f"Diagnostica senza cervello disponibile: {exc}", "assistant")
        return None


async def _converse(text: str, core_call) -> tuple[str, str, dict]:
    from features.agent import commands as agent_cmd
    if agent_cmd.weak(text) and not code.wanted(text):
        speech, ui = await agent_cmd.answer(text)
        return "agente · strumenti", speech, ui
    if actions.ACTIONISH.search(text):
        found = await _diagnose(text)
        if found:
            return "diagnostica · comando di sistema", *found
    data = await core_call(text)
    reply = data.get("speech_output") or "…"
    refused = bool(actions.REFUSAL.search(reply))
    if refused and not actions.ACTIONISH.search(text):
        found = await _diagnose(text)
        if found:
            return "diagnostica · comando di sistema", *found
    if refused and agent_cmd.enabled():
        speech, ui = await agent_cmd.answer(text)
        return "agente · strumenti", speech, ui
    if refused:
        actions.note_gap(text, "il modello ha rifiutato e nessuno strumento è adatto")
    return data.get("agent_id") or "core", *(code.answer(reply, text) or compose_generic(reply, text))
