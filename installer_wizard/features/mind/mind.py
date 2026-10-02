import json
import time
import uuid

from config import env_get
from state import store

from features.mind import extract, scoring
from features.mind.memory import MIND_DIR, LongTermMemory

STATE_FILE = MIND_DIR / "mind.json"
SKIP_STUDY = {"weather", "time", "system", "vision", "network", "brain", "music", "study", "voice_id"}
DEFAULTS = {"long_term": True, "study_feed": True, "llm_facts": True, "min_memorability": 0.5}


class Mind:
    def __init__(self) -> None:
        MIND_DIR.mkdir(parents=True, exist_ok=True)
        self.memory = LongTermMemory()
        self.settings = dict(DEFAULTS)
        self.diary: list = []
        self.counters = {"evaluated": 0, "stored": 0, "ignored": 0, "study": 0}
        self.views: dict = {}
        self.suggestions: list = []
        try:
            saved = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            self.settings.update({k: saved.get("settings", {}).get(k, v) for k, v in DEFAULTS.items()})
            self.diary = saved.get("diary", [])[:120]
            self.counters.update(saved.get("counters", {}))
            self.views = saved.get("views", {})
            self.suggestions = saved.get("suggestions", [])
        except (OSError, ValueError):
            pass
        self.publish()

    def enabled(self) -> bool:
        return env_get("JARVIS_MIND", "1") != "0"

    def save(self) -> None:
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"settings": self.settings, "diary": self.diary[:120],
                                   "counters": self.counters, "views": self.views,
                                   "suggestions": self.suggestions}, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(STATE_FILE)

    def publish(self) -> None:
        store.mind = {"enabled": self.enabled(), "facts": self.memory.stats()["count"],
                      "evaluated": self.counters["evaluated"], "stored": self.counters["stored"],
                      "last": self.diary[0] if self.diary else None}
        store.touch()

    def recall(self, query: str, who: str = "") -> str:
        if not self.enabled() or not self.settings.get("long_term"):
            return ""
        hits = self.memory.recall(query, k=4, who=who)
        return "\n".join(f"- ({h['kind']}) {h['text']}" for h in hits)

    async def evaluate(self, said: str, reply: str, intent: str, device: str, directed: bool, confidence: float,
                       ui_mode: str, agent: str, who: str = "") -> None:
        if not self.enabled() or not said:
            return
        try:
            from features.chat.dialogue import dialogue
            prior = dialogue.context(device)
        except Exception:
            prior = ""
        scores = scoring.evaluate(said, reply, intent, context_overlap=_overlap(prior, said))
        found = extract.facts(said) if directed else []
        if directed and self.settings.get("llm_facts") and scores["importance"] >= 0.4 and len(said) >= 20:
            found = self._merge(found, await self._llm_facts(said))
        reasons = []
        memory_route = "breve"
        stored = []
        if self.settings.get("long_term") and directed:
            if found:
                for f in found:
                    rec = self.memory.add(f["text"], f["kind"], score=max(0.6, scores["memorability"]), who=who)
                    if rec:
                        stored.append(rec["text"])
                memory_route = "lungo"
                reasons.append("fatto durevole riconosciuto")
            elif scores["memorability"] >= self.settings.get("min_memorability", 0.5) and len(said) >= 20:
                rec = self.memory.add(said[:160], "fatto", score=scores["memorability"], who=who)
                if rec:
                    stored.append(rec["text"])
                    memory_route = "lungo"
                    reasons.append("alta memorabilità")
        if memory_route == "breve":
            reasons.append("contesto effimero: resta nella memoria breve")
        is_study = bool(self.settings.get("study_feed") and directed and intent not in SKIP_STUDY
                        and len(said) >= 12 and scores["importance"] >= 0.4)
        widget = "" if ui_mode in ("", "face") else ui_mode
        if widget:
            reasons.append(f"ha richiamato una vista «{widget}»")
            self._suggest_widget(intent)
        if str(agent).startswith("algoritmo"):
            reasons.append("ha usato un algoritmo")
        self.counters["evaluated"] += 1
        if stored:
            self.counters["stored"] += 1
        if memory_route == "breve" and not stored:
            self.counters["ignored"] += 1
        if is_study:
            self.counters["study"] += 1
        entry = {"at": time.time(), "said": said[:200], "intent": intent, "directed": directed,
                 "confidence": round(confidence, 2), "scores": scores, "memory": memory_route,
                 "facts": stored, "study": is_study, "widget": widget,
                 "note": "; ".join(reasons) or "valutato"}
        self.diary = ([entry] + self.diary)[:120]
        self.save()
        self.publish()

    def _suggest_widget(self, intent: str) -> None:
        if not intent or intent in ("conversation", "action", "home"):
            return
        try:
            from features.desktop.desk import desk
            covered = any(intent in m.get("intents", []) for m in desk.widgets.values())
        except Exception:
            covered = True
        if covered:
            self.views.pop(intent, None)
            return
        self.views[intent] = self.views.get(intent, 0) + 1
        if self.views[intent] == 5 and not any(s.get("ref") == intent for s in self.suggestions):
            self.suggestions = ([{"id": uuid.uuid4().hex[:8], "ref": intent, "kind": "widget",
                                  "text": f"La risposta «{intent}» compare spesso con una vista ricca ma senza un "
                                          f"widget dedicato: posso prepararne uno su misura, se desidera.",
                                  "at": time.time()}] + self.suggestions)[:12]

    def dismiss(self, sid: str) -> bool:
        before = len(self.suggestions)
        self.suggestions = [s for s in self.suggestions if s["id"] != sid]
        if len(self.suggestions) != before:
            self.save()
            return True
        return False

    @staticmethod
    def _merge(a: list, b: list) -> list:
        out, seen = [], set()
        for f in (a + b):
            key = (f.get("text") or "").lower()[:40]
            if key and key not in seen:
                seen.add(key)
                out.append(f)
        return out[:4]

    async def _llm_facts(self, said: str) -> list:
        try:
            from features.brain.llm import generate
            result = await generate(
                said, as_json=True, max_tokens=240, temperature=0.1, kind="chat", govern=False,
                system=("Estrai i fatti DUREVOLI su chi parla, utili da ricordare a lungo (nome, preferenze, "
                        "lavoro, luoghi, relazioni, abitudini, obiettivi). Ignora domande, comandi e chiacchiere "
                        "effimere. Rispondi solo in JSON: "
                        '{"fatti": [{"tipo": "identita|preferenza|lavoro|luogo|relazione|abitudine|obiettivo|fatto", '
                        '"testo": "fatto conciso in terza persona"}]} (lista vuota se non c\'è nulla da ricordare).'))
        except Exception:
            return []
        items = result.get("fatti") if isinstance(result, dict) else None
        out = []
        for it in (items or [])[:4]:
            if isinstance(it, dict) and str(it.get("testo", "")).strip():
                out.append({"kind": str(it.get("tipo", "fatto"))[:20], "text": str(it["testo"]).strip()[:160]})
        return out

    def summary(self) -> dict:
        return {"enabled": self.enabled(), "settings": self.settings, "defaults": DEFAULTS,
                "counters": self.counters, "facts": self.memory.listing(), "facts_stats": self.memory.stats(),
                "suggestions": self.suggestions, "diary": self.diary[:60]}

    def update_settings(self, changes: dict) -> dict:
        for key, default in DEFAULTS.items():
            if key not in changes:
                continue
            if isinstance(default, bool):
                self.settings[key] = bool(changes[key])
            else:
                self.settings[key] = max(0.0, min(1.0, float(changes[key])))
        self.save()
        self.publish()
        return self.settings


def _overlap(prior: str, said: str) -> float:
    from features.mind import text as T
    return T.overlap(prior, said) if prior else 0.0


mind = Mind()
