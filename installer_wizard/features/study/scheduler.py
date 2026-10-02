import asyncio
import re
import time
from datetime import datetime

import httpx

from features.study.constants import LEVELS, log, now_day, slug
from state import store


class StudyScheduler:
    @staticmethod
    def _interest(topic: dict) -> float:
        age_days = (time.time() - topic.get("interest_at", topic["created"])) / 86400
        return topic.get("interest", 0.0) * 0.5 ** (age_days / 14)

    def _in_hours(self) -> bool:
        a, b = self.settings.get("hours_from", ""), self.settings.get("hours_to", "")
        if not (re.match(r"^\d{1,2}:\d{2}$", a or "") and re.match(r"^\d{1,2}:\d{2}$", b or "")):
            return True
        now = datetime.now().strftime("%H:%M").zfill(5)
        a, b = a.zfill(5), b.zfill(5)
        return a <= now < b if a <= b else (now >= a or now < b)

    def blocked(self) -> str:
        s, st = self.settings, self.data["stats"]
        if st.get("day") != now_day():
            st.update(day=now_day(), seconds_today=0)
        if not s.get("enabled"):
            return "off:Studio autonomo disattivato"
        if store.phase not in ("READY", "DEGRADED"):
            return "waiting:Jarvis non è ancora operativo"
        forced = time.time() < self.force_until
        if not forced:
            idle = time.time() - self.last_activity
            if idle < s["idle_minutes"] * 60:
                return f"waiting:Studierò dopo {int((s['idle_minutes'] * 60 - idle) // 60) + 1} minuti di riposo"
            if not self._in_hours():
                return f"hours:Fuori dalla fascia oraria di studio ({s['hours_from']}–{s['hours_to']})"
            if st["seconds_today"] >= s["daily_minutes"] * 60:
                return "budget:Tempo di studio di oggi esaurito"
        if self.external_busy and self.external_busy():
            return "waiting:Consolidamento nei pesi (Soup) in corso"
        sysinfo = store.system or {}
        if not forced and sysinfo.get("cpu_percent", 0) > s["max_cpu"]:
            return f"waiting:Processore occupato ({sysinfo['cpu_percent']:.0f}%)"
        if sysinfo.get("mem_percent", 0) > 93:
            return "waiting:Memoria quasi piena"
        return ""

    def _pick_topic(self) -> dict | None:
        active = [t for t in self.data["topics"].values() if t["status"] == "active"]
        if not active:
            return None

        def weight(t):
            hours = (time.time() - (t["last_studied"] or t["created"] - 86400)) / 3600
            return t["priority"] * (1 + min(self._interest(t), 5) / 5) * (hours + 1)
        return max(active, key=weight)

    def next_task(self) -> tuple | None:
        s, queue = self.settings, self.data["queue"]
        if s.get("auto_discover") and queue and (len(queue) >= 4 or time.time() - queue[0]["at"] > 1800):
            return ("discover", None)
        topic = self._pick_topic()
        if topic is None:
            due = [t for t in self.data["topics"].values()
                   if t["status"] == "done" and any(q.get("due", 0) <= time.time()
                                                    for lv in t["levels"].values() for q in self._questions(lv))]
            return ("review", due[0]) if due else None
        lvl = topic["levels"].get(str(topic["level"]))
        if not lvl or not lvl.get("lessons"):
            return ("plan", topic)
        due = [q for q in self._questions(lvl) if q.get("due", 0) <= time.time()]
        if len(due) >= 3:
            return ("review", topic)
        if any(x["status"] == "todo" for x in lvl["lessons"]):
            return ("lesson", topic)
        return ("exam", topic)

    async def run(self) -> None:
        await asyncio.sleep(45)
        while True:
            try:
                await self.tick()
            except Exception:
                log.exception("Errore nello studio autonomo")
            await asyncio.sleep(15)

    async def tick(self) -> None:
        reason = self.blocked()
        if reason:
            state, _, detail = reason.partition(":")
            if store.study.get("detail") != detail:
                self.publish(state, detail)
            return
        task = self.next_task()
        if task is None:
            self.publish("idle", "Tutte le materie sono in pari: aggiungine una o parlami dei tuoi interessi")
            return
        kind, topic = task
        started = time.time()
        self.current = asyncio.create_task(self.execute(kind, topic))
        try:
            await self.current
            self.data["stats"]["tasks"] += 1
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling():
                raise
            log.info("Studio interrotto dall'utente (%s)", kind)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            log.warning("Attività di studio «%s» non riuscita: %s", kind, exc)
            self.journal(f"⚠ {kind}: {exc}"[:200])
            self.publish("waiting", f"Nuovo tentativo tra poco ({type(exc).__name__})")
            await asyncio.sleep(120)
        finally:
            self.current = None
            spent = time.time() - started
            st = self.data["stats"]
            st["seconds_today"] += spent
            st["seconds_total"] += spent
            if topic:
                topic["seconds"] = topic.get("seconds", 0) + spent
            self.save()

    async def execute(self, kind: str, topic: dict | None) -> None:
        if kind == "discover":
            self.publish("studying", "Analizzo le conversazioni per capire cosa ti interessa")
            await self.discover()
        elif kind == "plan":
            self.publish("studying", f"Preparo il programma del livello {LEVELS[topic['level']]}", topic)
            await self.plan(topic)
        elif kind == "lesson":
            await self.lesson(topic)
        elif kind == "review":
            self.publish("studying", "Ripasso con domande di verifica", topic)
            await self.review(topic)
        elif kind == "exam":
            self.publish("studying", f"Esame di fine livello {LEVELS[topic['level']]}", topic)
            await self.exam(topic)

    async def discover(self) -> None:
        batch = self.data["queue"][:20]
        known = ", ".join(t["name"] for t in self.data["topics"].values()) or "nessuna"
        result = await self.llm_json(
            "Analizzi le domande di un utente al suo assistente per capire quali materie di studio gli interessano. "
            "Una materia è una disciplina (es. Elettronica, Cucina italiana, Storia romana, Programmazione Python, "
            "Astronomia), non un singolo fatto. Ignora saluti, meteo, orari, comandi alla casa e chiacchiere. "
            "Rispondi solo in JSON.",
            "Domande dell'utente:\n" + "\n".join(f"- {q['text']}" for q in batch)
            + f"\n\nMaterie già in studio: {known}.\n"
              'Formato: {"materie": [{"nome": "Nome della materia", "argomenti": ["argomento citato", "..."]}]} '
              "(lista vuota se nessuna domanda riguarda una materia).", 400)
        self.data["queue"] = self.data["queue"][len(batch):]
        for item in (result.get("materie") or [])[:6]:
            name = str(item.get("nome", "")).strip()
            if not (2 < len(name) <= 60):
                continue
            hints = [str(h)[:80] for h in (item.get("argomenti") or [])][:5]
            topic = self.find_topic(name)
            if topic:
                topic["interest"] = self._interest(topic) + 1
                topic["interest_at"] = time.time()
                topic["mentions"] += 1
                topic["hints"] = (hints + topic.get("hints", []))[:15]
                continue
            key = slug(name)
            m = self.data["mentions"].setdefault(key, {"name": name, "count": 0, "hints": []})
            m["count"] += 1
            m["last"] = time.time()
            m["hints"] = (hints + m["hints"])[:15]
            if m["count"] >= self.settings["min_mentions"]:
                t = self.add_topic(name, "auto", status="active" if self.settings["auto_accept"] else "proposed")
                t.update(interest=float(m["count"]), interest_at=time.time(), mentions=m["count"], hints=m["hints"])
                self.data["mentions"].pop(key, None)
                if t["status"] == "active":
                    store.event("INFO", f"Studio: nuova materia dalle conversazioni — {t['name']}", "study")
        self.save()
