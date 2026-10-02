import asyncio
import json
import time
from datetime import datetime

from features.study.constants import (DEFAULT_SETTINGS, DEPTH_TOKENS, LEVELS, SKIP_INTENTS, STATE_FILE, STUDY_DIR,
                                      now_day)
from features.study.lessons import StudyLessons
from features.study.memory_index import MemoryIndex
from features.study.recall import StudyRecall
from features.study.scheduler import StudyScheduler
from features.study.sources import StudySources
from features.study.topics import StudyTopics
from state import store


class StudyEngine(StudySources, StudyTopics, StudyScheduler, StudyLessons, StudyRecall):
    def __init__(self) -> None:
        STUDY_DIR.mkdir(parents=True, exist_ok=True)
        self.memory = MemoryIndex(STUDY_DIR / "memory")
        self.data = {"settings": dict(DEFAULT_SETTINGS), "topics": {}, "queue": [], "mentions": {},
                     "stats": {"day": now_day(), "seconds_today": 0, "seconds_total": 0, "lessons": 0,
                               "reviews": 0, "exams": 0, "tasks": 0}, "log": []}
        try:
            saved = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            self.data.update({k: v for k, v in saved.items() if k in self.data})
            self.data["settings"] = {**DEFAULT_SETTINGS, **saved.get("settings", {})}
        except (OSError, ValueError):
            pass
        self.last_activity = time.time()
        self.current: asyncio.Task | None = None
        self.activity_label = ""
        self.force_until = 0.0
        self.on_neuron = None
        self.external_busy = None
        self.embed_ok = True
        self.publish("waiting", "In attesa di un momento di riposo")

    def save(self) -> None:
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(STATE_FILE)
        self.memory.save()

    @property
    def settings(self) -> dict:
        return self.data["settings"]

    def journal(self, text: str) -> None:
        self.data["log"] = ([{"at": time.time(), "text": text}] + self.data["log"])[:80]

    def publish(self, state: str, detail: str = "", topic: dict | None = None) -> None:
        store.study = {"state": state, "detail": detail, "topic": topic["name"] if topic else "",
                       "level": LEVELS.get(topic["level"], "") if topic else "",
                       "cells": len(self.memory.ids), "today_minutes": round(self.data["stats"]["seconds_today"] / 60)}
        store.touch()

    def activity(self, source: str = "") -> None:
        self.last_activity = time.time()
        if self.current and not self.current.done():
            self.current.cancel()
            self.publish("paused", "Interrotto: ti ascolto")

    def note_query(self, text: str, intent: str) -> None:
        self.activity("chat")
        if intent in SKIP_INTENTS or len(text) < 12:
            return
        self.data["queue"] = (self.data["queue"] + [{"text": text[:400], "at": time.time()}])[-60:]
        self.save()

    def summary(self) -> dict:
        topics = [self.overview(t) for t in self.data["topics"].values()]
        topics.sort(key=lambda t: ({"active": 0, "proposed": 1, "paused": 2, "done": 3}.get(t["status"], 4), -t["priority"]))
        mentions = sorted(({"key": k, **v} for k, v in self.data["mentions"].items()), key=lambda m: -m["count"])[:12]
        return {"settings": self.settings, "status": store.study, "topics": topics, "mentions": mentions,
                "stats": {**self.data["stats"], "queue": len(self.data["queue"])}, "memory": self.memory.stats(),
                "journal": self.data["log"][:30], "levels": LEVELS, "defaults": DEFAULT_SETTINGS,
                "model": self._model(), "embed_model": self._embed_model()}

    def update_settings(self, changes: dict) -> dict:
        s = self.settings
        for key, default in DEFAULT_SETTINGS.items():
            if key not in changes:
                continue
            value = changes[key]
            if isinstance(default, bool):
                s[key] = bool(value)
            elif isinstance(default, int):
                s[key] = max(0, int(float(value)))
            else:
                s[key] = str(value).strip()[:60]
        s["idle_minutes"] = max(1, min(240, s["idle_minutes"]))
        s["max_cpu"] = max(10, min(100, s["max_cpu"]))
        s["daily_minutes"] = max(5, min(1440, s["daily_minutes"]))
        s["lessons_per_level"] = max(3, min(12, s["lessons_per_level"]))
        s["min_mentions"] = max(1, min(20, s["min_mentions"]))
        if s["depth"] not in DEPTH_TOKENS:
            s["depth"] = "normale"
        if not s["enabled"] and self.current and not self.current.done():
            self.current.cancel()
        self.save()
        return s

    def study_now(self, minutes: int = 30) -> None:
        self.force_until = time.time() + minutes * 60
        self.last_activity = 0


engine = StudyEngine()


def speech_summary() -> tuple[str, dict]:
    s = engine.summary()
    active = [t for t in s["topics"] if t["status"] in ("active", "done")]
    if not active:
        return ("Per ora non sto studiando nessuna materia. Può indicarmele dal pannello, sezione Studio, "
                "oppure parlarmi dei suoi interessi: imparo da solo ciò che le serve.", {"mode": "face"})
    st = s["status"] or {}
    lead = active[0]
    speech = (f"Sto studiando {len(active)} {'materia' if len(active) == 1 else 'materie'}. "
              f"{lead['name']} è al livello {lead['level_name'].lower()}, avanzamento {lead['progress'] * 100:.0f} per cento. ")
    if st.get("state") == "studying" and st.get("detail"):
        speech += f"In questo momento: {st['detail'].lower()}."
    stats = [{"label": f"{t['name']} · {t['level_name']}", "value": f"{t['progress'] * 100:.0f}%",
              "percent": t["progress"] * 100} for t in active[:8]]
    items = [{"label": j["text"], "value": datetime.fromtimestamp(j["at"]).strftime("%d/%m %H:%M"), "status": ""}
             for j in s["journal"][:8]]
    return speech, {"mode": "focus", "title": "Cosa sto studiando",
                    "subtitle": f"{s['memory']['cells']} celle di memoria · {round(s['stats']['seconds_total'] / 3600, 1)} ore di studio",
                    "panels": [{"type": "stats", "title": "Materie", "items": stats},
                               {"type": "list", "title": "Diario di studio",
                                "items": items or [{"label": "Nessuna attività ancora", "value": "", "status": ""}]}]}
