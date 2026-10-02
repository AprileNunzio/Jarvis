import asyncio
import json
import logging
import time
from datetime import datetime

from config import STATE_DIR
from state import store

from features.automations import sun

log = logging.getLogger("jarvis.automations")
VARS_FILE = STATE_DIR / "automation_vars.json"
LEAVE_AFTER = 120


class States:
    def __init__(self) -> None:
        self.virtual: dict[str, dict] = {}
        self.globals: dict = self._load()
        self.seen: dict[str, float] = {}

    @staticmethod
    def _load() -> dict:
        try:
            return json.loads(VARS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def save_globals(self) -> None:
        tmp = VARS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.globals, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(VARS_FILE)

    @staticmethod
    def _home():
        try:
            from features.home_assistant.home import brain
            return brain
        except Exception:
            return None

    def get(self, eid: str) -> dict | None:
        if eid.startswith("jarvis.var."):
            name = eid[len("jarvis.var."):]
            if name in self.globals:
                return {"state": self.globals[name], "attrs": {}, "lc": self.virtual.get(eid, {}).get("lc", 0)}
            return None
        if eid == "sun.sun" and not self._home_has(eid):
            return sun.entity()
        if eid in self.virtual:
            return self.virtual[eid]
        home = self._home()
        if home and eid in home.states:
            return home.states[eid]
        return None

    def _home_has(self, eid: str) -> bool:
        home = self._home()
        return bool(home and eid in home.states)

    def state(self, eid: str, default=""):
        st = self.get(eid)
        return default if st is None else st.get("state", default)

    def attr(self, eid: str, name: str, default=""):
        st = self.get(eid)
        return default if st is None else (st.get("attrs") or {}).get(name, default)

    def since(self, eid: str) -> float:
        st = self.get(eid)
        return time.time() - float(st.get("lc") or time.time()) if st else 0.0

    def people(self) -> list[str]:
        return [p["name"] for p in (store.presence or {}).get("people", []) if p.get("known")]

    def present(self, who: str = "") -> bool:
        people = (store.presence or {}).get("people", [])
        if not who:
            return bool(people)
        w = str(who).lower()
        return any(w in (p.get("name", "").lower(), p.get("slug", "").lower()) or
                   p.get("name", "").lower().split(" ")[0] == w for p in people if p.get("known"))

    def quiet(self) -> bool:
        try:
            from features.sounds.policy import policy
            return policy.quiet()
        except Exception:
            return False

    def set_virtual(self, eid: str, value, attrs: dict | None = None) -> tuple[dict | None, dict]:
        old = self.virtual.get(eid)
        if old and old.get("state") == value and (attrs is None or attrs == old.get("attrs")):
            return old, old
        new = {"state": value, "attrs": attrs or {}, "lc": time.time()}
        self.virtual[eid] = new
        return old, new

    def catalog(self) -> list[dict]:
        out = []
        home = self._home()
        if home:
            for eid, st in list(home.states.items()):
                e = home.entities.get(eid, {}) if hasattr(home, "entities") else {}
                out.append({"id": eid, "name": e.get("name") or (st.get("attrs") or {}).get("friendly_name") or eid,
                            "state": st.get("state"), "source": "casa", "domain": eid.split(".")[0]})
        for eid, st in self.virtual.items():
            out.append({"id": eid, "name": st.get("attrs", {}).get("name", eid), "state": st.get("state"),
                        "source": "jarvis", "domain": eid.split(".")[1] if eid.count(".") > 1 else "jarvis"})
        for k, v in self.globals.items():
            out.append({"id": f"jarvis.var.{k}", "name": f"Variabile {k}", "state": v, "source": "variabile",
                        "domain": "var"})
        if not self._home_has("sun.sun"):
            s = sun.entity()
            out.append({"id": "sun.sun", "name": "Sole", "state": s["state"], "source": "jarvis", "domain": "sun"})
        return sorted(out, key=lambda x: (x["source"], x["id"]))


class Bus:
    def __init__(self) -> None:
        self.states = States()
        self.listeners: list = []
        self.waiters: list[tuple[callable, asyncio.Future]] = []
        self.recent: list[dict] = []
        self.present: dict[str, float] = {}
        self.components: dict[str, str] = {}

    def listen(self, fn) -> None:
        self.listeners.append(fn)

    def emit(self, name: str, data: dict | None = None) -> None:
        ev = {"name": name, "data": data or {}, "at": time.time()}
        if not (name == "state_changed" and str((data or {}).get("entity_id", "")).startswith(("jarvis.time", "jarvis.component."))):
            self.recent = (self.recent + [ev])[-100:]
        for check, fut in list(self.waiters):
            if not fut.done() and check(ev):
                fut.set_result(ev)
        for fn in self.listeners:
            try:
                fn(ev)
            except Exception as exc:
                log.warning("Automazioni: evento %s non gestito: %s", name, exc)

    def wait(self, check, timeout: float):
        fut = asyncio.get_event_loop().create_future()
        item = (check, fut)
        self.waiters.append(item)

        async def waiting():
            try:
                return await asyncio.wait_for(fut, timeout)
            except asyncio.TimeoutError:
                return None
            finally:
                if item in self.waiters:
                    self.waiters.remove(item)
        return waiting()

    def state_changed(self, eid: str, old: dict | None, new: dict | None) -> None:
        self.emit("state_changed", {"entity_id": eid, "from": (old or {}).get("state"), "to": (new or {}).get("state"),
                                    "old": old or {}, "new": new or {}})

    def set_state(self, eid: str, value, attrs: dict | None = None) -> None:
        old, new = self.states.set_virtual(eid, value, attrs)
        if old is not new:
            self.state_changed(eid, old, new)

    def set_global(self, name: str, value) -> None:
        eid = f"jarvis.var.{name}"
        old = {"state": self.states.globals.get(name)} if name in self.states.globals else None
        if old and old["state"] == value:
            return
        self.states.globals[name] = value
        self.states.virtual[eid] = {"state": value, "attrs": {}, "lc": time.time()}
        self.states.save_globals()
        self.state_changed(eid, old, {"state": value})

    def presence(self, visible: list[dict]) -> None:
        now = time.time()
        for p in visible:
            if not p.get("known"):
                continue
            slug = p["slug"]
            if slug not in self.present:
                self.emit("person_arrived", {"person": p["name"], "slug": slug})
                self.set_state(f"jarvis.person.{slug}", "home", {"name": p["name"]})
            self.present[slug] = now
        for slug, seen in list(self.present.items()):
            if now - seen > LEAVE_AFTER:
                del self.present[slug]
                name = self.states.virtual.get(f"jarvis.person.{slug}", {}).get("attrs", {}).get("name", slug)
                self.emit("person_left", {"person": name, "slug": slug})
                self.set_state(f"jarvis.person.{slug}", "away", {"name": name})
        count = len(self.present)
        before = self.states.virtual.get("jarvis.people", {}).get("state")
        self.set_state("jarvis.people", count, {"name": "Persone in vista"})
        if before not in (None, 0) and count == 0:
            self.emit("nobody_home", {})
        if before == 0 and count > 0:
            self.emit("somebody_home", {})

    def component(self, key: str, label: str, status: str) -> None:
        old = self.components.get(key)
        self.components[key] = status
        self.set_state(f"jarvis.component.{key}", status, {"name": label})
        if old is not None and old != status:
            self.emit("component_broken" if status not in ("ok", "idle") else "component_ok",
                      {"component": key, "label": label, "status": status})

    def tick(self) -> None:
        self.set_state("jarvis.time", datetime.now().strftime("%H:%M"), {"name": "Ora"})


bus = Bus()


def emit(name: str, data: dict | None = None) -> None:
    try:
        bus.emit(name, data)
    except Exception as exc:
        log.debug("Evento %s ignorato: %s", name, exc)
