import asyncio
import logging
import re
import time
from datetime import datetime, timedelta

from config import env_get
from state import store

from features.automations import sun
from features.automations.bus import bus
from features.automations.conditions import compare
from features.automations.expr import ExprError, evaluate, number, render, wrap
from features.automations.library import library
from features.automations.runner import Run, Runner, Stop

log = logging.getLogger("jarvis.automations")
TICK = 1.0
TEMPLATE_EVERY = 10


def enabled() -> bool:
    return env_get("JARVIS_AUTOMATIONS", "1") != "0"


class Engine:
    def __init__(self) -> None:
        self.runner = Runner(self)
        self.active: dict[str, Run] = {}
        self.recent: list[dict] = []
        self.queues: dict[str, list] = {}
        self.fired: dict[str, float] = {}
        self.marks: dict[str, str] = {}
        self.pending: dict[str, asyncio.Task] = {}
        self.template_state: dict[str, bool] = {}
        self.rev = 0
        self.status = "in avvio"
        bus.listen(self.on_event)

    def touch(self) -> None:
        self.rev += 1

    def set_enabled(self, ref: str, value: bool) -> str:
        a = library.get(ref)
        library.patch(a["id"], enabled=value)
        return f"«{a['name']}» {'attivata' if value else 'disattivata'}"

    async def start_by_ref(self, ref: str, trigger: dict, wait: bool = False) -> str:
        a = library.get(ref)
        run = self.start(a, trigger, check=False)
        if not run:
            return f"«{a['name']}» non avviata"
        if wait and run.task:
            await asyncio.wait({run.task})
            return f"«{a['name']}»: {run.status}"
        return f"«{a['name']}» avviata"

    def start(self, a: dict, trigger: dict, check: bool = True, force: bool = False) -> Run | None:
        if not force and (not enabled() or not a.get("enabled", True)):
            return None
        now = time.time()
        if check and a.get("cooldown") and now - self.fired.get(a["id"], 0) < a["cooldown"]:
            return None
        running = [r for r in self.active.values() if r.automation == a["id"]]
        mode = a.get("mode", "single")
        if running and mode == "single" and not force:
            return None
        run = Run(a, trigger)
        if check and a.get("conditions"):
            if not self.runner.checker.all(a["conditions"], self.runner.ctx(run), run.trace):
                run.status, run.ended = "condizioni non soddisfatte", time.time()
                self._remember(run, store_it=trigger.get("type") not in ("state", "template", "interval"))
                return None
        self.fired[a["id"]] = now
        if running and mode == "restart":
            for r in running:
                if r.task:
                    r.task.cancel()
        if running and mode == "queued":
            q = self.queues.setdefault(a["id"], [])
            if len(q) < a.get("max", 10):
                q.append(run)
                run.status = "in coda"
                return run
            return None
        if running and mode == "parallel" and len(running) >= a.get("max", 10):
            return None
        self._launch(a, run)
        return run

    def _launch(self, a: dict, run: Run) -> None:
        self.active[run.id] = run
        run.task = asyncio.get_event_loop().create_task(self._run(a, run))

    async def _run(self, a: dict, run: Run) -> None:
        run.status = "in corso"
        self.touch()
        try:
            await self.runner.execute(a.get("actions"), run)
            run.status = "completata"
        except Stop as s:
            run.status = "errore" if s.error else "fermata"
            run.error = s.reason
        except asyncio.CancelledError:
            run.status = "interrotta"
        except Exception as exc:
            run.status, run.error = "errore", str(exc)
            log.warning("Automazione «%s»: %s", a["name"], exc)
        finally:
            run.ended = time.time()
            self.active.pop(run.id, None)
            self._remember(run)
            if run.status == "errore":
                store.event("WARN", f"Automazione «{a['name']}»: {run.error}", "automazioni")
            bus.emit("automation_finished", {"automation": a["name"], "id": a["id"], "status": run.status})
            q = self.queues.get(a["id"])
            if q:
                nxt = q.pop(0)
                self._launch(library.items.get(a["id"], a), nxt)

    def _remember(self, run: Run, store_it: bool = True) -> None:
        view = run.view(full=True)
        self.recent = ([view] + self.recent)[:60]
        if store_it:
            library.record(view)
        self.touch()

    def stop(self, rid: str) -> bool:
        run = self.active.get(rid)
        if run and run.task:
            run.task.cancel()
            return True
        return False

    def on_event(self, ev: dict) -> None:
        if not enabled():
            return
        name, data = ev["name"], ev["data"]
        for a in list(library.items.values()):
            if not a.get("enabled", True):
                continue
            for t in a.get("triggers") or []:
                kind = t["type"]
                try:
                    if kind == "state" and name == "state_changed":
                        self._state_trigger(a, t, data)
                    elif kind == "template" and name == "state_changed":
                        self._template_trigger(a, t)
                    elif kind == "presence" and name == t.get("event"):
                        who = str(t.get("person") or "").lower()
                        if not who or who in str(data.get("person", "")).lower() or who == data.get("slug"):
                            self.start(a, {**t, "data": data, "label": f"presenza: {name}"})
                    elif kind == "event":
                        wanted = t.get("custom") if t.get("name") == "custom" else t.get("name")
                        if name == wanted and (not t.get("filter") or self._filter(t["filter"], data)):
                            self.start(a, {**t, "data": data, "label": f"evento {name}"})
                except (ExprError, ValueError, KeyError, TypeError) as exc:
                    log.debug("Innesco %s di «%s»: %s", kind, a["name"], exc)

    def _filter(self, expr: str, data: dict) -> bool:
        return bool(evaluate(expr, {**self.runner.names({}), "data": wrap(data)}))

    @staticmethod
    def _value(t: dict, st: dict):
        if not st:
            return None
        return (st.get("attrs") or {}).get(t["attribute"]) if t.get("attribute") else st.get("state")

    def _matches(self, t: dict, value, old_value=None, check_old: bool = True) -> bool:
        if t.get("to") not in (None, "") and str(value).lower() != str(t["to"]).lower():
            return False
        if check_old and t.get("from") not in (None, "") and str(old_value).lower() != str(t["from"]).lower():
            return False
        if t.get("above") not in (None, "") and not compare(value, ">", t["above"]):
            return False
        if t.get("below") not in (None, "") and not compare(value, "<", t["below"]):
            return False
        return True

    def _state_trigger(self, a: dict, t: dict, data: dict) -> None:
        names = self.runner.names({"vars": a.get("variables") or {}})
        eid = str(render(t["entity"], names))
        if data.get("entity_id") != eid:
            return
        t = {**t, **render({k: t.get(k) for k in ("to", "from", "above", "below", "attribute")}, names)}
        new, old = self._value(t, data.get("new")), self._value(t, data.get("old"))
        if new == old:
            return
        key = f"{a['id']}:{t['id']}"
        if key in self.pending:
            self.pending.pop(key).cancel()
        if not self._matches(t, new, old):
            return
        if (t.get("above") not in (None, "") or t.get("below") not in (None, "")) and old is not None \
                and self._matches(t, old, None, check_old=False) and not t.get("to"):
            return
        trig = {**t, "data": {"entity_id": eid, "from": old, "to": new}, "label": f"{eid}: {old} → {new}"}
        hold = number(t.get("for"), 0)
        if not hold:
            self.start(a, trig)
            return

        async def later():
            await asyncio.sleep(hold)
            self.pending.pop(key, None)
            if self._matches(t, self._value(t, bus.states.get(eid)), None, check_old=False):
                self.start(a, trig)
        self.pending[key] = asyncio.get_event_loop().create_task(later())

    def _template_trigger(self, a: dict, t: dict) -> None:
        key = f"{a['id']}:{t['id']}"
        try:
            now_true = bool(evaluate(t["expr"], self.runner.names({})))
        except ExprError:
            now_true = False
        was = self.template_state.get(key)
        self.template_state[key] = now_true
        if not now_true:
            if key in self.pending:
                self.pending.pop(key).cancel()
            return
        if was is not False:
            return
        hold = number(t.get("for"), 0)
        trig = {**t, "label": f"espressione vera: {t['expr'][:60]}"}
        if not hold:
            self.start(a, trig)
            return

        async def later():
            await asyncio.sleep(hold)
            self.pending.pop(key, None)
            if self.template_state.get(key):
                self.start(a, trig)
        self.pending[key] = asyncio.get_event_loop().create_task(later())

    def _clock(self) -> None:
        now = datetime.now()
        stamp = now.strftime("%Y-%m-%d %H:%M")
        hm = now.strftime("%H:%M")
        for a in list(library.items.values()):
            if not a.get("enabled", True):
                continue
            for t in a.get("triggers") or []:
                key = f"{a['id']}:{t['id']}"
                kind = t["type"]
                if kind == "time":
                    at = str(t.get("at") or "")
                    if len(at) == 4:
                        at = "0" + at
                    if at == hm and self.marks.get(key) != stamp and (not t.get("days") or now.weekday() in [int(d) for d in t["days"]]):
                        self.marks[key] = stamp
                        self.start(a, {**t, "label": f"ore {hm}"})
                elif kind == "interval":
                    every = max(1.0, number(t.get("minutes"), 60)) * 60
                    last = float(self.marks.get(key) or 0)
                    if not last:
                        self.marks[key] = str(time.time())
                    elif time.time() - last >= every:
                        self.marks[key] = str(time.time())
                        self.start(a, {**t, "label": f"ogni {int(every / 60)} minuti"})
                elif kind == "sun":
                    target = sun.times(now.date()).get(t.get("event") or "sunset")
                    if target:
                        moment = (target + timedelta(minutes=number(t.get("offset"), 0))).strftime("%Y-%m-%d %H:%M")
                        if moment == stamp and self.marks.get(key) != stamp:
                            self.marks[key] = stamp
                            self.start(a, {**t, "label": "alba" if t.get("event") == "sunrise" else "tramonto"})

    def webhook(self, key: str, data: dict) -> list[str]:
        started = []
        for a in list(library.items.values()):
            for t in a.get("triggers") or []:
                if t["type"] == "webhook" and t.get("key") == key:
                    if self.start(a, {**t, "data": data, "label": "webhook"}):
                        started.append(a["name"])
        return started

    def phrase(self, text: str) -> tuple[dict, dict, dict] | None:
        clean = re.sub(r"^\s*(ehi\s+)?jarvis[,\s]+", "", text.strip(), flags=re.I).strip(" .!?").lower()
        for a in library.all():
            if not a.get("enabled", True):
                continue
            for t in a.get("triggers") or []:
                if t["type"] != "phrase":
                    continue
                for p in t.get("phrases") or []:
                    pattern = re.escape(str(p).strip(" .!?").lower()).replace(r"\*", "(.+?)")
                    m = re.fullmatch(pattern, clean)
                    if m:
                        return a, t, {"frase": clean, "parole": [g.strip() for g in m.groups()]}
        return None

    async def run(self) -> None:
        await asyncio.sleep(20)
        last_place, last_template = 0.0, 0.0
        while True:
            try:
                if enabled() and store.phase in ("READY", "DEGRADED"):
                    self.status = "attivo"
                    if not self.marks.get("startup"):
                        self.marks["startup"] = "1"
                        bus.emit("startup", {})
                    bus.tick()
                    self._clock()
                    for key, comp in list((store.components or {}).items()):
                        bus.component(key, comp.get("label", key), comp.get("status") or "")
                    if time.time() - last_template > TEMPLATE_EVERY:
                        last_template = time.time()
                        for a in list(library.items.values()):
                            for t in a.get("triggers") or []:
                                if a.get("enabled", True) and t["type"] == "template":
                                    self._template_trigger(a, t)
                    if time.time() - last_place > 3600:
                        last_place = time.time()
                        try:
                            from features.location.locator import locator
                            here = await locator.current(refresh=False)
                            sun.set_place(here.get("lat"), here.get("lon"), here.get("name") or "")
                        except Exception as exc:
                            log.debug("Posizione per il sole non disponibile: %s", exc)
                else:
                    self.status = "disattivato" if not enabled() else "in attesa del sistema"
            except Exception as exc:
                log.warning("Motore automazioni: %s", exc)
            await asyncio.sleep(TICK)


engine = Engine()
