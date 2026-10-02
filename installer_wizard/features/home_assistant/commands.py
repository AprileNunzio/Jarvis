import asyncio
import json
import time

from config import DEMO
from features.home_assistant.connection import HAError
from features.home_assistant.constants import (CANCEL_RE, CONFIRM_RE, CONFIRM_WINDOW, DOMAIN_PLURAL, INFINITIVE,
                                               LLM_DATA_KEYS, PAST, STATE_IT, log)
from features.home_assistant.helpers import join_words
from features.home_assistant.nlu.calls import is_sensitive
from features.home_assistant.nlu.matching import match_areas, match_domains
from features.home_assistant.nlu.parser import looks_like_home, parse
from features.home_assistant.nlu.text import norm, stem
from state import store


class HomeCommands:
    async def execute(self, plan: dict, text: str = "", source: str = "voce") -> dict:
        started = time.time()
        errors = []
        if DEMO:
            await asyncio.sleep(0.03)
            for call in plan["calls"]:
                self._demo_apply(call)
        else:
            async def one(call):
                try:
                    await self._call({"type": "call_service", "domain": call["domain"], "service": call["service"],
                                      "service_data": call.get("data") or {},
                                      "target": {"entity_id": call["entity_ids"]}}, 15)
                except (HAError, asyncio.TimeoutError) as exc:
                    errors.append(f"{call['domain']}.{call['service']}: {exc}")
            await asyncio.gather(*(one(c) for c in plan["calls"]))
        ms = int((time.time() - started) * 1000)
        ok = not errors
        self.stats["commands"] += 1
        self.stats["avg_ms"] = round(ms if self.stats["commands"] == 1 else self.stats["avg_ms"] * 0.8 + ms * 0.2)
        args = (time.time(), text[:300], json.dumps(plan, default=str), int(ok), ms, source)
        await asyncio.to_thread(self.db.run, lambda c: c.execute("INSERT INTO commands VALUES (?,?,?,?,?,?)", args))
        return {"ok": ok, "errors": errors, "ms": ms}

    def describe_plan(self, plan: dict) -> str:
        parts = []
        for call in plan["calls"]:
            verb = PAST.get(call["service"], "comandato")
            if call["domain"] == "scene" and call["service"] == "turn_on":
                verb = "attivato"
            if call["domain"] == "script" and call["service"] == "turn_on":
                verb = "eseguito"
            ids = call["entity_ids"]
            areas = {self.entities.get(x, {}).get("area_id") for x in ids}
            if len(ids) > 3:
                what = f"{len(ids)} {DOMAIN_PLURAL.get(call['domain'], 'dispositivi')}"
                if len(areas) == 1 and (a := self.areas.get(next(iter(areas)) or "")):
                    what += f" in {a['name']}"
            else:
                what = join_words([self.entities.get(x, {}).get("name", x) for x in ids])
            d = call.get("data") or {}
            extra = ""
            if "brightness_pct" in d:
                extra += f" al {d['brightness_pct']}%"
            if "rgb_color" in d:
                extra += f" di {plan.get('params', {}).get('color_name', 'colore scelto')}"
            if "color_temp_kelvin" in d:
                extra += " con luce " + ("calda" if d["color_temp_kelvin"] < 3500 else "fredda" if d["color_temp_kelvin"] > 5000 else "naturale")
            if "position" in d:
                extra += f" al {d['position']}%"
            if "temperature" in d:
                extra += f" a {str(d['temperature']).rstrip('0').rstrip('.')} gradi"
            if "hvac_mode" in d:
                extra += f" in {STATE_IT.get(d['hvac_mode'], d['hvac_mode'])}"
            if "percentage" in d:
                extra += f" al {d['percentage']}%"
            if "volume_level" in d:
                extra += f" al {round(d['volume_level'] * 100)}%"
            if "brightness_step_pct" in d:
                verb = "aumentato la luce di" if d["brightness_step_pct"] > 0 else "abbassato la luce di"
            if call["service"] == "set_temperature" and "temperature" in d and "brightness" not in verb:
                verb = "impostato"
            parts.append(f"{verb} {what}{extra}")
        return "Ho " + join_words(parts) + "." if parts else "Fatto."

    async def llm_plan(self, text: str) -> dict | None:
        t = norm(text)
        tokens = [stem(w) for w in t.split()]
        area_ids, _ = match_areas(tokens, self.catalog)
        domains = match_domains(tokens)
        ents = [e for e in self.catalog.entities.values()
                if (not area_ids or e.get("area_id") in area_ids) and (not domains or e["domain"] in domains)]
        if len(ents) > 150:
            ents = ents[:150]
        if not ents:
            return None
        lines = [f"{e['entity_id']} | {e['name']} | {self.areas.get(e.get('area_id') or '', {}).get('name', '-')} | "
                 f"{e.get('state')} | servizi: {', '.join(self.services.get(e['domain'], [])[:14])}" for e in ents]
        prompt = (
            "Sei il sistema domotico di Jarvis collegato a Home Assistant. Traduci la richiesta dell'utente in "
            "chiamate di servizio usando SOLO le entità elencate. Rispondi solo con JSON nel formato "
            '{"calls": [{"entity_id": "light.x", "service": "turn_on", "data": {"brightness_pct": 50}}]}. '
            'Se la richiesta non è un comando per queste entità rispondi {"calls": []}. '
            "Chiavi ammesse in data: " + ", ".join(sorted(LLM_DATA_KEYS)) + ".\n\nEntità (id | nome | stanza | stato | "
            "servizi):\n" + "\n".join(lines) + f"\n\nRichiesta: {text}\nJSON:")
        from features.brain.llm import BrainUnavailable, generate
        try:
            spec = await generate(prompt, as_json=True, max_tokens=300, temperature=0, kind="chat", timeout=60)
        except (BrainUnavailable, ValueError) as exc:
            log.info("Traduzione domotica non riuscita: %s", exc)
            return None
        return self._validate_llm(spec if isinstance(spec, dict) else {})

    def _validate_llm(self, spec: dict) -> dict | None:
        calls: dict = {}
        sensitive = False
        for c in (spec or {}).get("calls") or []:
            if not isinstance(c, dict):
                continue
            eid, service = str(c.get("entity_id", "")), str(c.get("service", ""))
            e = self.catalog.entities.get(eid)
            if not e or service not in self.services.get(e["domain"], []):
                continue
            data = {k: v for k, v in (c.get("data") or {}).items()
                    if k in LLM_DATA_KEYS and isinstance(v, (int, float, str, bool, list))}
            sensitive = sensitive or is_sensitive(e["domain"], service, e)
            key = (e["domain"], service, json.dumps(data, sort_keys=True))
            calls.setdefault(key, {"domain": e["domain"], "service": service, "entity_ids": [], "data": data})
            calls[key]["entity_ids"].append(eid)
        if not calls:
            return None
        return {"kind": "command", "action": "llm", "calls": list(calls.values()),
                "entities": [x for c in calls.values() for x in c["entity_ids"]], "sensitive": sensitive,
                "how": "cervello"}

    async def _learn(self, text: str, plan: dict) -> None:
        key = norm(text)
        self.learned[key] = plan
        args = (key, json.dumps(plan), 1, time.time())
        await asyncio.to_thread(self.db.run, lambda c: c.execute("INSERT OR REPLACE INTO learned VALUES (?,?,?,?)", args))

    async def handle(self, text: str) -> tuple[str, dict, str] | None:
        s = self.settings()
        if not self.entities or not DEMO and not (s["enabled"] and s["url"] and s["token"]):
            return None
        if self.pending and time.time() < self.pending["until"]:
            if CONFIRM_RE.match(text):
                plan, self.pending = self.pending["plan"], None
                return await self._run(plan, text, "conferma")
            if CANCEL_RE.match(text):
                self.pending = None
                return "Come desidera, non faccio nulla.", {"mode": "face"}, "casa"
        self.pending = None
        started = time.time()
        plan = parse(text, self.catalog)
        source = "regole"
        if plan is None and (learned := self.learned.get(norm(text))):
            plan, source = learned, "memoria"
            self.stats["learned_hits"] += 1
        if plan is None and looks_like_home(text) and self.online:
            plan, source = await self.llm_plan(text), "cervello"
            if plan:
                self.stats["llm"] += 1
                await self._learn(text, plan)
        if plan is None:
            return None
        if plan["kind"] == "query":
            speech, ui = self.answer(plan)
            return speech, ui, f"casa · risposta ({int((time.time() - started) * 1000)} ms)"
        if plan["kind"] == "ask":
            return plan["speech"], {"mode": "face"}, "casa"
        if plan["kind"] == "unsupported":
            names = join_words([self.entities.get(x, {}).get("name", x) for x in plan["entities"][:3]])
            return f"Non so fare questa operazione con {names}.", {"mode": "face"}, "casa"
        if not self.online:
            return ("Home Assistant non è raggiungibile in questo momento: riprovo a collegarmi da solo.",
                    {"mode": "face"}, "casa")
        if plan.get("sensitive") and self.settings()["confirm"]:
            self.pending = {"plan": plan, "until": time.time() + CONFIRM_WINDOW}
            what = join_words([f"{INFINITIVE.get(c['service'], 'comandare')} "
                          f"{join_words([self.entities.get(x, {}).get('name', x) for x in c['entity_ids']])}"
                          for c in plan["calls"]])
            return (f"Signore, per sicurezza chiedo conferma: devo davvero {what}? Risponda «conferma» oppure «annulla».",
                    {"mode": "face"}, "casa · conferma")
        return await self._run(plan, text, source, started)

    async def _run(self, plan: dict, text: str, source: str, started: float | None = None) -> tuple[str, dict, str]:
        started = started or time.time()
        res = await self.execute(plan, text, source)
        total = int((time.time() - started) * 1000)
        if not res["ok"]:
            store.event("WARN", f"Comando per la casa non riuscito: {'; '.join(res['errors'])[:300]}", "home")
            return ("Home Assistant non ha eseguito il comando: " + res["errors"][0].split(": ", 1)[-1] + ".",
                    {"mode": "face"}, f"casa · {source}")
        return self.describe_plan(plan), {"mode": "face"}, f"casa · {source} ({total} ms)"
