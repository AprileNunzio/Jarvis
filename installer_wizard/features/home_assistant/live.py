import asyncio
import json
import time

from features.home_assistant.connection import HAError
from features.home_assistant.constants import FLUSH_EVERY, HISTORY_DAYS, MOTION, OPENING, PRESENCE, TRACKED, log
from features.home_assistant.helpers import ago, parse_ts
from state import store


class HomeLive:
    def _on_event(self, ev: dict) -> None:
        etype = ev.get("event_type")
        if etype != "state_changed":
            self._schedule_resync()
            return
        data = ev.get("data") or {}
        eid, new = data.get("entity_id"), data.get("new_state")
        if not eid:
            return
        if new is None:
            self.states.pop(eid, None)
            self._schedule_resync()
            return
        old = self.states.get(eid, {})
        st = {"state": new.get("state"), "attrs": new.get("attributes") or {}, "lc": parse_ts(new.get("last_changed"))}
        self.states[eid] = st
        self._dirty_states[eid] = st
        e = self.entities.get(eid)
        if e is None:
            self._schedule_resync()
            return
        c = self.catalog.entities.get(eid)
        if c is not None:
            c["state"], c["attrs"] = st["state"], st["attrs"]
        if old.get("state") != st["state"] or old.get("attrs") != st["attrs"]:
            from features.automations.bus import bus as automation_bus
            automation_bus.state_changed(eid, old or None, st)
        if old.get("state") == st["state"]:
            return
        dc = e.get("device_class") or st["attrs"].get("device_class") or ""
        kind = None
        if e["domain"] == "binary_sensor" and dc in MOTION | PRESENCE:
            kind = "motion" if dc in MOTION else "presence"
            if e.get("area_id"):
                self.last_motion[e["area_id"]] = time.time()
        elif e["domain"] == "binary_sensor" and dc in OPENING:
            kind = "opening"
        elif e["domain"] in TRACKED:
            kind = e["domain"]
        elif e["domain"] in ("light", "cover", "climate", "media_player") and st["state"] != "unavailable":
            kind = e["domain"]
        if kind:
            self._activity.append((time.time(), e.get("area_id"), eid, kind, st["state"]))
        if kind in ("motion", "presence", "person"):
            self._update_occupancy()

    def _schedule_resync(self) -> None:
        if self._resync and not self._resync.done():
            return

        async def later():
            await asyncio.sleep(3)
            try:
                await self.sync("modifica in Home Assistant")
            except (HAError, asyncio.TimeoutError) as exc:
                log.info("Nuovo studio della casa non riuscito: %s", exc)
        self._resync = asyncio.create_task(later())

    async def _flusher(self) -> None:
        last_prune = 0.0
        while True:
            await asyncio.sleep(FLUSH_EVERY)
            try:
                if int(time.time()) % 30 < FLUSH_EVERY:
                    self._update_occupancy()
                if not self._dirty_states and not self._activity:
                    continue
                dirty, self._dirty_states = self._dirty_states, {}
                acts, self._activity = self._activity, []
                prune = time.time() - last_prune > 3600
                if prune:
                    last_prune = time.time()

                def write(c):
                    now = time.time()
                    c.executemany("INSERT OR REPLACE INTO states VALUES (?,?,?,?,?)",
                                  [(k, v["state"], json.dumps(v["attrs"], default=str), v["lc"], now)
                                   for k, v in dirty.items()])
                    c.executemany("INSERT INTO activity VALUES (?,?,?,?,?)", acts)
                    if prune:
                        c.execute("DELETE FROM activity WHERE ts < ?", (now - HISTORY_DAYS * 86400,))
                        c.execute("DELETE FROM commands WHERE ts < ?", (now - HISTORY_DAYS * 86400,))
                await asyncio.to_thread(self.db.run, write)
            except Exception:
                log.exception("Scrittura del database della casa")

    def _init_motion(self) -> None:
        now = time.time()
        for eid, e in self.entities.items():
            st = self.states.get(eid)
            if not st or e["domain"] != "binary_sensor" or not e.get("area_id"):
                continue
            if (e.get("device_class") or st["attrs"].get("device_class")) in MOTION | PRESENCE:
                ts = now if st["state"] == "on" else st["lc"]
                self.last_motion[e["area_id"]] = max(self.last_motion.get(e["area_id"], 0), ts)
        self._update_occupancy()

    def _sensors(self, aid: str, classes: set, domain: str = "binary_sensor") -> list[dict]:
        out = []
        for eid in self.area_entities.get(aid, []):
            e, st = self.entities.get(eid), self.states.get(eid)
            if e and st and e["domain"] == domain and not e.get("disabled") and \
                    (e.get("device_class") or st["attrs"].get("device_class")) in classes:
                out.append({"entity_id": eid, "name": e["name"], "state": st["state"], "since": st["lc"],
                            "class": e.get("device_class") or st["attrs"].get("device_class")})
        return out

    def room_status(self, aid: str) -> dict:
        s = self.settings()
        motion = self._sensors(aid, MOTION)
        presence = self._sensors(aid, PRESENCE)
        now = time.time()
        moving = [x for x in motion if x["state"] == "on"]
        present = [x for x in presence if x["state"] == "on"]
        last = self.last_motion.get(aid, 0)
        webcam = bool(self.catalog.default_area == aid and any(p.get("known") is not None
                                                               for p in store.presence.get("people", [])))
        recent = last and now - last < s["motion_min"] * 60
        occupied = bool(moving or present or recent or webcam)
        if present:
            label = "presenza rilevata"
        elif moving:
            label = "movimento adesso"
        elif webcam:
            label = "Jarvis vede qualcuno"
        elif recent:
            label = f"movimento {ago(last)}"
        elif motion or presence:
            label = f"libera · ultimo movimento {ago(last)}" if last else "libera"
        else:
            label = "nessun sensore di presenza"
        temps = self._sensors(aid, {"temperature"}, "sensor")
        hums = self._sensors(aid, {"humidity"}, "sensor")
        opened = [x for x in self._sensors(aid, OPENING) if x["state"] == "on"]
        lights = [eid for eid in self.area_entities.get(aid, []) if eid.startswith("light.")
                  and (self.states.get(eid) or {}).get("state") == "on" and self.entities[eid].get("controllable")]

        def num(xs):
            vals = []
            for x in xs:
                try:
                    vals.append(float(x["state"]))
                except (TypeError, ValueError):
                    pass
            return round(sum(vals) / len(vals), 1) if vals else None
        temperature = num(temps)
        if temperature is None:
            for eid in self.area_entities.get(aid, []):
                if eid.startswith("climate.") and (t := (self.states.get(eid) or {}).get("attrs", {}).get("current_temperature")) is not None:
                    temperature = t
                    break
        return {"area_id": aid, "name": self.areas.get(aid, {}).get("name", aid), "occupied": occupied, "label": label,
                "has_sensors": bool(motion or presence), "motion": [x["name"] for x in moving],
                "presence": [x["name"] for x in present], "last_motion": last or None,
                "temperature": temperature, "humidity": num(hums), "open": [x["name"] for x in opened],
                "lights_on": len(lights), "devices": sum(1 for d in self.devices.values() if d["area_id"] == aid),
                "floor": self.floors.get(self.areas.get(aid, {}).get("floor_id") or "", {}).get("name", "")}

    def _update_occupancy(self) -> None:
        occ = [aid for aid in self.areas if self.room_status(aid)["occupied"]]
        if occ != self.occupied:
            self.occupied = occ
            self.catalog.occupied = list(occ)
            self.rev += 1
            store.touch()

    def people_home(self) -> list[dict]:
        out = []
        for eid, e in self.entities.items():
            if e["domain"] == "person" and (st := self.states.get(eid)):
                out.append({"name": e["name"], "state": st["state"], "since": st["lc"],
                            "home": st["state"] == "home"})
        return out
