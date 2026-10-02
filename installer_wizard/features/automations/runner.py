import asyncio
import re
import time
import uuid

from features.automations import actions as leaf
from features.automations.bus import bus
from features.automations.conditions import Checker
from features.automations.expr import ExprError, evaluate, functions, number, render, wrap

MAX_STEPS = 2000
MAX_LOOPS = 1000
MAX_WAIT = 24 * 3600
YES = re.compile(r"^\s*(s[iì]|certo|conferm\w*|procedi|vai|ok|okay|va bene|fallo|esatto)\b", re.I)


class Stop(Exception):
    def __init__(self, reason: str = "", error: bool = False) -> None:
        super().__init__(reason)
        self.reason, self.error = reason, error


class Run:
    def __init__(self, auto: dict, trigger: dict) -> None:
        self.id = uuid.uuid4().hex[:10]
        self.automation, self.name = auto["id"], auto["name"]
        self.trigger = trigger
        self.vars = dict(auto.get("variables") or {})
        self.trace: list[dict] = []
        self.status = "in corso"
        self.started, self.ended = time.time(), 0.0
        self.error, self.response, self.waiting = "", "", ""
        self.steps = 0
        self.chat = False
        self.task: asyncio.Task | None = None

    def view(self, full: bool = False) -> dict:
        out = {"id": self.id, "automation": self.automation, "name": self.name, "status": self.status,
               "started": self.started, "ended": self.ended, "error": self.error, "waiting": self.waiting,
               "trigger": {k: v for k, v in self.trigger.items() if k in ("id", "type", "label", "by")},
               "steps": len(self.trace), "ms": int(((self.ended or time.time()) - self.started) * 1000)}
        if full:
            out["trace"] = self.trace
            out["vars"] = {k: (v if isinstance(v, (int, float, bool, str)) or v is None else str(v)[:300])
                           for k, v in self.vars.items()}
        return out


class Runner:
    def __init__(self, engine) -> None:
        self.engine = engine
        self.checker = Checker(bus.states, self.names)
        self.asking: list[tuple[Run, asyncio.Future]] = []

    def names(self, ctx) -> dict:
        run = ctx if isinstance(ctx, Run) else None
        base = functions(bus.states)
        variables = run.vars if run else (ctx or {}).get("vars", {})
        trigger = run.trigger if run else (ctx or {}).get("trigger", {})
        tdata = (trigger or {}).get("data") or {}
        base.update({k: wrap(v) for k, v in tdata.items() if isinstance(k, str) and k.isidentifier() and k not in base})
        base.update({k: wrap(v) for k, v in variables.items() if isinstance(k, str) and k.isidentifier()})
        base.update({"vars": wrap(variables), "trigger": wrap(trigger), "data": wrap((trigger or {}).get("data") or {}),
                     "globals": wrap(bus.states.globals)})
        return base

    def ctx(self, run: Run) -> dict:
        return {"vars": run.vars, "trigger": run.trigger}

    async def execute(self, items: list, run: Run, path: str = "") -> None:
        for i, a in enumerate(items or []):
            await self.step(a, run, f"{path}{i + 1}")

    async def step(self, a: dict, run: Run, path: str) -> None:
        run.steps += 1
        if run.steps > MAX_STEPS:
            raise Stop("troppi passi: possibile ciclo infinito", True)
        if a.get("enabled") is False:
            run.trace.append({"path": path, "kind": "azione", "type": a["type"], "ok": True, "detail": "saltata (disattivata)", "ms": 0})
            return
        entry = {"path": path, "kind": "azione", "type": a["type"], "label": a.get("label", ""), "ok": True, "detail": "", "ms": 0}
        run.trace.append(entry)
        started = time.time()
        try:
            entry["detail"] = await self._do(a, run, path) or ""
        except Stop:
            entry["detail"] = "fermata"
            raise
        except asyncio.CancelledError:
            entry.update(ok=False, detail="interrotta")
            raise
        except Exception as exc:
            entry.update(ok=False, detail=f"errore: {exc}")
            if not a.get("continue_on_error"):
                raise Stop(f"{a['type']} ({path}): {exc}", True)
        finally:
            entry["ms"] = int((time.time() - started) * 1000)
            self.engine.touch()

    async def _do(self, a: dict, run: Run, path: str) -> str:
        kind, names = a["type"], self.names(run)
        if kind == "if":
            ok = self.checker.all(a.get("conditions"), self.ctx(run), run.trace)
            await self.execute(a.get("then") if ok else a.get("else"), run, f"{path}.{'allora' if ok else 'altrimenti'}.")
            return "condizioni vere" if ok else "condizioni false"
        if kind == "choose":
            for j, opt in enumerate(a.get("options") or []):
                if self.checker.all(opt.get("conditions"), self.ctx(run), run.trace):
                    await self.execute(opt.get("actions"), run, f"{path}.caso{j + 1}.")
                    return f"caso {j + 1}"
            await self.execute(a.get("default"), run, f"{path}.altrimenti.")
            return "nessun caso: altrimenti"
        if kind == "parallel":
            branches = a.get("branches") or []
            await asyncio.gather(*(self.execute(b, run, f"{path}.ramo{j + 1}.") for j, b in enumerate(branches)))
            return f"{len(branches)} rami completati"
        if kind == "repeat":
            return await self._repeat(a, run, path)
        if kind == "delay":
            seconds = self._seconds(render(a.get("seconds"), names))
            run.waiting = f"attesa di {int(seconds)} s"
            try:
                await asyncio.sleep(seconds)
            finally:
                run.waiting = ""
            return f"atteso {int(seconds)} s"
        if kind in ("wait_state", "wait_event", "wait_expr"):
            return await self._wait(a, run, names)
        if kind == "confirm":
            return await self._confirm(a, run, path, names)
        if kind == "set":
            value = render(a.get("value"), names)
            if a.get("scope") == "global":
                bus.set_global(str(a["name"]), value)
            else:
                run.vars[str(a["name"])] = value
            return f"{a['name']} = {str(value)[:80]}"
        if kind == "stop":
            raise Stop(str(render(a.get("reason") or "fermata dall'automazione", names)), bool(a.get("error")))
        if kind == "respond":
            run.response = str(render(a.get("text"), names))
            return run.response[:200]
        if kind == "run":
            return await self.engine.start_by_ref(str(a.get("automation")), {"type": "run", "by": run.name},
                                                  wait=bool(a.get("wait")))
        if kind == "toggle":
            return self.engine.set_enabled(str(a.get("automation")), a.get("enabled", True) is not False)
        fn = leaf.LEAF.get(kind)
        if not fn:
            raise ValueError(f"azione sconosciuta {kind}")
        params = render({k: v for k, v in a.items() if k not in ("id", "type")}, names)
        return await fn(params, run)

    @staticmethod
    def _seconds(value) -> float:
        text = str(value).strip()
        if re.fullmatch(r"\d+:\d{2}(:\d{2})?", text):
            parts = [int(x) for x in text.split(":")]
            value = parts[0] * 3600 + parts[1] * 60 + parts[2] if len(parts) == 3 else parts[0] * 60 + parts[1]
        return max(0.0, min(MAX_WAIT, number(value)))

    async def _repeat(self, a: dict, run: Run, path: str) -> str:
        count = int(number(a.get("count"), 0)) if a.get("count") not in (None, "") else None
        done = 0
        while done < MAX_LOOPS:
            names = self.names(run)
            if count is not None and done >= count:
                break
            if a.get("while") and not evaluate(a["while"], names):
                break
            run.vars["ripetizione"] = done + 1
            await self.execute(a.get("actions"), run, f"{path}.giro{done + 1}.")
            done += 1
            if a.get("until") and evaluate(a["until"], self.names(run)):
                break
            if count is None and not a.get("while") and not a.get("until"):
                break
            await asyncio.sleep(0)
        return f"{done} ripetizioni"

    async def _wait(self, a: dict, run: Run, names: dict) -> str:
        timeout = min(MAX_WAIT, number(a.get("timeout"), 300) or 300)
        kind = a["type"]
        if kind == "wait_state":
            eid, want = str(render(a["entity"], names)), str(render(a["to"], names))
            if str(bus.states.state(eid)) == want:
                return f"{eid} era già {want}"
            run.waiting = f"attendo {eid} = {want}"
            check = lambda ev: ev["name"] == "state_changed" and ev["data"].get("entity_id") == eid and str(ev["data"].get("to")) == want
            got = await bus.wait(check, timeout)
        elif kind == "wait_event":
            name = a.get("custom") if a.get("name") == "custom" else a.get("name")
            flt = a.get("filter")
            run.waiting = f"attendo l'evento {name}"

            def check(ev):
                if ev["name"] != name:
                    return False
                if not flt:
                    return True
                try:
                    return bool(evaluate(flt, {**names, "data": wrap(ev["data"])}))
                except ExprError:
                    return False
            got = await bus.wait(check, timeout)
            if got:
                run.vars["evento"] = got["data"]
        else:
            deadline, got = time.time() + timeout, None
            run.waiting = f"attendo che {a['expr']}"
            while time.time() < deadline:
                if evaluate(a["expr"], self.names(run)):
                    got = True
                    break
                await bus.wait(lambda ev: ev["name"] == "state_changed", min(5.0, max(0.1, deadline - time.time())))
        run.waiting = ""
        if got:
            return "condizione raggiunta"
        if a.get("continue", True) is False:
            raise Stop("tempo di attesa scaduto", True)
        run.vars["scaduto"] = True
        return f"scaduto dopo {int(timeout)} s, continuo"

    async def _confirm(self, a: dict, run: Run, path: str, names: dict) -> str:
        question = str(render(a.get("question"), names))
        if run.chat and not run.response:
            run.response = question
        else:
            leaf.say(question, run, force=True, icon="❓")
        fut = asyncio.get_event_loop().create_future()
        item = (run, fut)
        self.asking.append(item)
        run.waiting = f"attendo risposta a «{question[:60]}»"
        try:
            answer = await asyncio.wait_for(fut, min(MAX_WAIT, number(a.get("timeout"), 60) or 60))
        except asyncio.TimeoutError:
            answer = None
        finally:
            run.waiting = ""
            if item in self.asking:
                self.asking.remove(item)
        yes = bool(answer)
        run.vars["risposta"] = "sì" if yes else ("no" if answer is not None else "nessuna")
        await self.execute(a.get("yes") if yes else a.get("no"), run, f"{path}.{'sì' if yes else 'no'}.")
        return f"risposta: {run.vars['risposta']}"

    def answer(self, text: str) -> str | None:
        if not self.asking:
            return None
        run, fut = self.asking[-1]
        if not fut.done():
            fut.set_result(bool(YES.search(text)))
        return run.name
