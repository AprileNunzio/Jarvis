import asyncio
import json
import logging
import time
from datetime import datetime

from config import STATE_DIR, env_get
from state import store

from features.automations import sun
from features.automations.bus import bus
from features.habits.journal import ACTIONABLE, Journal
from features.habits.miner import WINDOW_DAYS, mine

log = logging.getLogger("jarvis.habits")
FILE = STATE_DIR / "habits.json"
OWN_ACTION = 15
ASK_EVERY = 2 * 3600
ANSWER_WITHIN = 180
SNOOZE = 3 * 86400
ALARM_AGAIN = 3600
ODD_CLASSES = {"door", "window", "opening", "garage_door", "motion", "occupancy", "presence"}


def enabled() -> bool:
    return env_get("JARVIS_HABITS", "1") != "0"


def threshold() -> float:
    try:
        return max(0.5, min(0.95, float(env_get("JARVIS_HABITS_CONFIDENCE", "0.7"))))
    except ValueError:
        return 0.7


class Habits:
    def __init__(self) -> None:
        self.journal = Journal()
        self.commanded: dict[str, float] = {}
        self.asking: tuple[str, float] | None = None
        self.last_arrival = 0.0
        self.alarmed: dict[str, float] = {}
        try:
            self.data = json.loads(FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {"suggestions": {}, "mined": 0, "asked": 0, "anomalies": []}
        bus.listen(self.on_event)

    def _save(self) -> None:
        tmp = FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(FILE)

    def mark_commanded(self, entities: list[str]) -> None:
        now = time.time()
        for e in entities or ["all"]:
            self.commanded[e] = now

    def _own(self, eid: str) -> bool:
        now = time.time()
        return now - self.commanded.get(eid, 0) < OWN_ACTION or now - self.commanded.get("all", 0) < OWN_ACTION

    def on_event(self, ev: dict) -> None:
        if not enabled():
            return
        name, data = ev["name"], ev["data"]
        people = len(bus.present)
        if name == "state_changed":
            eid = str(data.get("entity_id", ""))
            new, old = data.get("to"), data.get("from")
            domain = eid.split(".")[0]
            if new in (None, "unavailable", "unknown") or old in (None, "unavailable", "unknown") or new == old:
                return
            if domain in ACTIONABLE and not self._own(eid):
                self.journal.add(ev["at"], eid, new, people, sun.up(), "action")
            elif domain == "binary_sensor" and new == "on":
                cls = bus.states.attr(eid, "device_class", "")
                if cls in ODD_CLASSES:
                    self.journal.add(ev["at"], eid, new, people, sun.up(), "sensor")
                    self._check_odd(eid, cls, people)
        elif name in ("person_arrived", "somebody_home") and ev["at"] - self.last_arrival > 600:
            self.last_arrival = ev["at"]
            self.journal.add(ev["at"], "presence", "arrived", people, sun.up(), "arrival")

    def _check_odd(self, eid: str, cls: str, people: int) -> None:
        if people or env_get("JARVIS_HABITS_ANOMALIES", "1") == "0":
            return
        now = time.time()
        rows = self.journal.rows(now - WINDOW_DAYS * 86400, "sensor")
        if not rows or now - rows[0][0] < 7 * 86400 or now - self.alarmed.get(eid, 0) < ALARM_AGAIN:
            return
        cur = datetime.now().hour * 60 + datetime.now().minute
        usual = [r for r in rows[:-1] if r[1] == eid and min(abs(r[4] - cur), 1440 - abs(r[4] - cur)) <= 60]
        if usual:
            return
        self.alarmed[eid] = now
        label = bus.states.attr(eid, "friendly_name", eid)
        what = "si è aperto" if cls in ("door", "window", "opening", "garage_door") else "ha rilevato movimento"
        text = f"Signore, situazione insolita: {label} {what} alle {datetime.now():%H:%M} e in casa non vedo nessuno."
        self.data["anomalies"] = ([{"at": now, "entity": eid, "text": text}] + self.data.get("anomalies", []))[:50]
        self._save()
        bus.emit("habit_anomaly", {"entity": eid, "label": label, "text": text})
        from features.desktop.desk import desk
        desk.show("notice", {"icon": "🚨", "title": "Situazione insolita", "text": text, "level": "warn",
                             "announce": True, "speak": text}, key=f"odd:{eid}", ttl=600)
        try:
            from features.sounds.policy import policy
            policy.play("alert", reason="situazione insolita")
        except Exception:
            pass

        async def telegram():
            try:
                from features.telegram.bot import bot
                await bot.notify("🚨 " + text)
            except Exception as exc:
                log.debug("Telegram non disponibile: %s", exc)
        asyncio.get_event_loop().create_task(telegram())

    def analyse(self) -> list[dict]:
        names = {e["id"]: e["name"] for e in bus.states.catalog()}
        found = mine(self.journal.rows(time.time() - WINDOW_DAYS * 86400), names, threshold())
        known = self.data["suggestions"]
        for s in found:
            old = known.get(s["id"])
            if old and old["status"] in ("accepted", "rejected"):
                old.update(confidence=s["confidence"], support=s["support"], observed=s["observed"])
                continue
            known[s["id"]] = {**(old or {"status": "new", "created": time.time()}), **s,
                              "status": (old or {}).get("status", "new")}
        self.data["mined"] = time.time()
        self.journal.prune()
        self._save()
        return found

    def pending(self) -> list[dict]:
        now = time.time()
        return sorted([s for s in self.data["suggestions"].values()
                       if s["status"] == "new" or (s["status"] == "snoozed" and now > s.get("until", 0))],
                      key=lambda s: -s["confidence"])

    def decide(self, sid: str, verdict: str) -> str:
        s = self.data["suggestions"][sid]
        if verdict == "accept":
            from features.automations.library import library
            a = library.add({**s["automation"], "enabled": True}, origin="abitudini")
            s.update(status="accepted", automation=a["id"], decided=time.time())
            message = f"Fatto, signore: da ora {s['text']} ci penso io."
        elif verdict == "snooze":
            s.update(status="snoozed", until=time.time() + SNOOZE)
            message = "Come desidera, ne riparliamo tra qualche giorno."
        else:
            s.update(status="rejected", decided=time.time())
            message = "Come desidera, non lo automatizzo."
        self.asking = None
        self._save()
        store.touch()
        return message

    def _ask(self) -> None:
        if not enabled() or env_get("JARVIS_HABITS_ASK", "1") == "0" or not bus.present or bus.states.quiet():
            return
        now = time.time()
        if now - self.data.get("asked", 0) < ASK_EVERY or not 9 <= datetime.now().hour < 21:
            return
        todo = self.pending()
        if not todo:
            return
        s = todo[0]
        self.asking = (s["id"], now)
        self.data["asked"] = now
        s["asked"] = now
        self._save()
        text = f"Signore, ho notato che {s['text']}. Vuole che me ne occupi io d'ora in poi?"
        from features.desktop.desk import desk
        desk.show("notice", {"icon": "💡", "title": "Proposta di automazione", "text": text, "announce": True, "speak": text},
                  key="habit-ask", ttl=ANSWER_WITHIN)

    def waiting(self) -> str | None:
        if self.asking and time.time() - self.asking[1] < ANSWER_WITHIN:
            return self.asking[0]
        self.asking = None
        return None

    async def run(self) -> None:
        await asyncio.sleep(120)
        while True:
            try:
                if enabled() and store.phase in ("READY", "DEGRADED"):
                    now = datetime.now()
                    if time.time() - self.data.get("mined", 0) > 86400 or (now.hour == 4 and time.time() - self.data.get("mined", 0) > 3600):
                        await asyncio.to_thread(self.analyse)
                    self._ask()
            except Exception as exc:
                log.warning("Abitudini: %s", exc)
            await asyncio.sleep(60)


habits = Habits()
