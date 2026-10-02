import json
import time

from features.home_assistant.constants import PROTO_LABEL, STATE_IT
from features.home_assistant.helpers import CAP_IT, join_words
from features.home_assistant.nlu.parser import parse
from features.home_assistant.nlu.text import norm
from state import store


def discovered() -> list[str]:
    try:
        from features.network.explorer import explorer
        return sorted({f"http://{d['ip']}:8123" for d in explorer.devices.values()
                       if d.get("type") == "homeassistant" and d.get("ip")})
    except Exception:
        return []


class HomeReports:
    def protocol_stats(self) -> list[dict]:
        counts: dict = {}
        devs = [d for d in self.devices.values() if not d["disabled"]]
        for d in devs:
            counts[d["protocol"]] = counts.get(d["protocol"], 0) + 1
        matter = sum(1 for d in devs if d["matter"])
        out = [{"key": p, "label": PROTO_LABEL.get(p, p), "value": str(n), "percent": round(n * 100 / max(1, len(devs)))}
               for p, n in sorted(counts.items(), key=lambda x: -x[1])]
        if matter:
            out.append({"key": "matter_all", "label": "di cui Matter", "value": str(matter),
                        "percent": round(matter * 100 / max(1, len(devs)))})
        return out

    def summary_line(self) -> str:
        devs = [d for d in self.devices.values() if not d["disabled"] and d["protocol"] != "virtual"]
        counts: dict = {}
        for d in devs:
            counts[d["protocol"]] = counts.get(d["protocol"], 0) + 1
        top = join_words([f"{n} {PROTO_LABEL.get(p, p)}" for p, n in sorted(counts.items(), key=lambda x: -x[1])[:4]])
        ctrl = sum(1 for e in self.entities.values() if e.get("controllable"))
        return (f"{len(self.areas)} stanze, {len(devs)} dispositivi" + (f" ({top})" if top else "")
                + f", {len(self.entities)} entità di cui {ctrl} comandabili")

    def brief(self) -> dict:
        return {"status": self.status, "rev": self.rev,
                "occupied": [self.areas[a]["name"] for a in self.occupied if a in self.areas]}

    def overview(self) -> dict:
        s = self.settings()
        rooms = [self.room_status(a) for a in sorted(self.areas, key=lambda a: (
            str(self.areas[a].get("floor_id") or ""), self.areas[a]["name"]))]
        for r in rooms:
            r["aliases"] = self.aliases.get(f"area:{r['area_id']}", [])
            r["ha_aliases"] = self.areas[r["area_id"]]["aliases"]
        motion_rooms = sum(1 for r in rooms if r["has_sensors"])
        return {"status": self.status, "error": self.error, "ha_version": self.ha_version, "ha_name": self.ha_name,
                "url": s["url"], "configured": bool(s["url"] and s["token"]), "room": s["room"],
                "connected_at": self.connected_at, "synced_at": self.synced_at, "sync_ms": self.sync_ms,
                "counts": {"floors": len(self.floors), "areas": len(self.areas),
                           "devices": sum(1 for d in self.devices.values() if not d["disabled"]),
                           "entities": len(self.entities),
                           "controllable": sum(1 for e in self.entities.values() if e.get("controllable")),
                           "motion_rooms": motion_rooms, "learned": len(self.learned)},
                "protocols": self.protocol_stats(), "rooms": rooms, "people": self.people_home(),
                "stats": self.stats, "summary": self.summary_line() if self.entities else "",
                "floors": [{"floor_id": f["floor_id"], "name": f["name"]} for f in self.floors.values()],
                "pending": bool(self.pending), "discovered": discovered()}

    def device_list(self) -> dict:
        out = []
        for d in self.devices.values():
            ents = []
            for eid in d["entities"]:
                e = self.entities.get(eid)
                if not e or e["disabled"]:
                    continue
                ents.append({"entity_id": eid, "name": e["name"], "domain": e["domain"],
                             "state": self._state_text(e), "controllable": bool(e.get("controllable")),
                             "capabilities": [CAP_IT.get(c, c) for c in e.get("capabilities", [])],
                             "category": e["category"], "aliases": e["aliases"] + self.aliases.get(f"entity:{eid}", []),
                             "jarvis_aliases": self.aliases.get(f"entity:{eid}", [])})
            out.append({k: d[k] for k in ("device_id", "name", "manufacturer", "model", "model_id", "sw_version",
                                          "hw_version", "integration", "protocol", "matter", "area_id", "disabled")}
                       | {"area": self.areas.get(d["area_id"] or "", {}).get("name", ""),
                          "protocol_label": PROTO_LABEL.get(d["protocol"], d["protocol"]),
                          "via": self.devices.get(d["via_device_id"] or "", {}).get("name", ""), "entities": ents})
        loose = [{"entity_id": e["entity_id"], "name": e["name"], "domain": e["domain"], "state": self._state_text(e),
                  "area": self.areas.get(e.get("area_id") or "", {}).get("name", "")}
                 for e in self.entities.values() if not e.get("device_id") and e.get("controllable")]
        return {"devices": sorted(out, key=lambda d: (d["area"] or "~", d["name"])), "loose": loose,
                "protocols": PROTO_LABEL, "areas": [{"area_id": a, "name": x["name"]} for a, x in self.areas.items()]}

    def activity(self, hours: int = 24, limit: int = 200) -> list[dict]:
        rows = self.db.query("SELECT ts, area_id, entity_id, kind, state FROM activity WHERE ts > ? "
                             "ORDER BY ts DESC LIMIT ?", (time.time() - hours * 3600, limit))
        pending = [r for r in reversed(self._activity) if r[0] > time.time() - hours * 3600]
        return [{"ts": r[0], "area": self.areas.get(r[1] or "", {}).get("name", ""),
                 "name": self.entities.get(r[2], {}).get("name", r[2]), "kind": r[3],
                 "state": STATE_IT.get(r[4], r[4])} for r in (pending + rows)[:limit]]

    def commands(self, limit: int = 50) -> list[dict]:
        rows = self.db.query("SELECT ts, text, ok, ms, source FROM commands ORDER BY ts DESC LIMIT ?", (limit,))
        return [{"ts": r[0], "text": r[1], "ok": bool(r[2]), "ms": r[3], "source": r[4]} for r in rows]

    def set_aliases(self, target: str, names: list[str]) -> None:
        kind, _, key = target.partition(":")
        if kind not in ("area", "entity") or (kind == "area" and key not in self.areas) or \
                (kind == "entity" and key not in self.entities):
            raise KeyError(target)
        clean = list(dict.fromkeys(n.strip()[:60] for n in names if n and n.strip()))[:12]
        if clean:
            self.aliases[target] = clean
            self.db.run(lambda c: c.execute("INSERT OR REPLACE INTO aliases VALUES (?, ?)", (target, json.dumps(clean))))
        else:
            self.aliases.pop(target, None)
            self.db.run(lambda c: c.execute("DELETE FROM aliases WHERE target=?", (target,)))
        self._rebuild_catalog()
        self.rev += 1

    def forget_learned(self) -> None:
        self.learned.clear()
        self.db.run(lambda c: c.execute("DELETE FROM learned"))

    async def test(self, text: str, run: bool) -> dict:
        started = time.time()
        plan = parse(text, self.catalog) or self.learned.get(norm(text))
        parse_ms = round((time.time() - started) * 1000, 2)
        if run:
            out = await self.handle(text)
            return {"plan": plan, "parse_ms": parse_ms, "speech": out[0] if out else None,
                    "agent": out[2] if out else None}
        speech = None
        if plan and plan["kind"] == "query":
            speech = self.answer(plan)[0]
        elif plan and plan["kind"] == "command":
            speech = "(prova) " + self.describe_plan(plan)
        elif plan and plan["kind"] == "ask":
            speech = plan["speech"]
        return {"plan": plan, "parse_ms": parse_ms, "speech": speech, "agent": "regole" if plan else None}

    def _demo_apply(self, call: dict) -> None:
        for eid in call["entity_ids"]:
            st = self.states.get(eid)
            if not st:
                continue
            svc = call["service"]
            new = {"turn_on": "on", "turn_off": "off", "open_cover": "open", "close_cover": "closed",
                   "lock": "locked", "unlock": "unlocked", "media_play": "playing", "media_pause": "paused"}.get(svc)
            if svc == "toggle":
                new = "off" if st["state"] == "on" else "on"
            data = call.get("data") or {}
            if "brightness_pct" in data:
                st["attrs"]["brightness"] = round(data["brightness_pct"] * 2.55)
            if "temperature" in data:
                st["attrs"]["temperature"] = data["temperature"]
            if new and new != st["state"]:
                st["state"], st["lc"] = new, time.time()
            if eid in self.catalog.entities:
                self.catalog.entities[eid]["state"] = st["state"]
        self.rev += 1
        store.touch()
