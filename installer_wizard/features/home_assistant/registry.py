import asyncio
import json
import time

from features.home_assistant.connection import HAError
from features.home_assistant.constants import (BT_INT, CLOUD_INT, LAN_INT, VIRTUAL_INT, WIFI_INT, ZIGBEE_HUBS,
                                               ZIGBEE_INT, ZWAVE_INT, log)
from features.home_assistant.helpers import capabilities, parse_ts
from features.home_assistant.nlu.matching import Catalog, DOMAIN_PRIORITY, area_names
from features.home_assistant.nlu.text import find_phrase, norm, phrase_stems
from features.home_assistant.nlu.vocabulary import DOMAIN_PHRASES
from state import store


class HomeRegistry:
    async def sync(self, reason: str = "") -> None:
        started = time.time()
        cfg = await self._call({"type": "get_config"})
        areas = await self._call({"type": "config/area_registry/list"})
        try:
            floors = await self._call({"type": "config/floor_registry/list"})
        except HAError:
            floors = []
        devices = await self._call({"type": "config/device_registry/list"}, 60)
        entities = await self._call({"type": "config/entity_registry/list"}, 60)
        try:
            entries = await self._call({"type": "config_entries/get"}, 30)
        except HAError:
            entries = []
        states = await self._call({"type": "get_states"}, 60)
        services = await self._call({"type": "get_services"}, 30)
        extended: dict = {}
        ids = [e["entity_id"] for e in entities if not e.get("disabled_by")]
        for i in range(0, len(ids), 400):
            try:
                extended.update(await self._call({"type": "config/entity_registry/get_entries",
                                                  "entity_ids": ids[i:i + 400]}, 30) or {})
            except HAError:
                break
        self._ingest(cfg=cfg, floors=floors, areas=areas, devices=devices, entities=entities, entries=entries,
                     states=states, services=services, extended=extended)
        self.sync_ms = int((time.time() - started) * 1000)
        await asyncio.to_thread(self._persist_registries)
        asyncio.create_task(self._matter_diagnostics())
        log.info("Casa studiata (%s) in %d ms: %s", reason, self.sync_ms, self.summary_line())

    def _ingest(self, cfg: dict, floors: list, areas: list, devices: list, entities: list, entries: list,
                states: list, services: dict, extended: dict) -> None:
        self.ha_name = (cfg or {}).get("location_name", "") or self.ha_name
        entry_domain = {e.get("entry_id"): e.get("domain") for e in entries or []}
        self.floors = {f["floor_id"]: {"floor_id": f["floor_id"], "name": f.get("name", ""), "level": f.get("level"),
                                       "aliases": list(f.get("aliases") or [])} for f in floors or []}
        self.areas = {a["area_id"]: {"area_id": a["area_id"], "name": a.get("name", ""), "floor_id": a.get("floor_id"),
                                     "aliases": list(a.get("aliases") or []), "icon": a.get("icon") or ""}
                      for a in areas or []}
        self.states = {s["entity_id"]: {"state": s.get("state"), "attrs": s.get("attributes") or {},
                                        "lc": parse_ts(s.get("last_changed"))} for s in states or []}
        self.services = {d: sorted((v or {}).keys()) for d, v in (services or {}).items()}
        devs = {}
        for d in devices or []:
            integration = entry_domain.get(d.get("primary_config_entry")) or next(
                (entry_domain[c] for c in d.get("config_entries") or [] if c in entry_domain), None) or next(
                (i[0] for i in d.get("identifiers") or [] if i), "")
            devs[d["id"]] = {"device_id": d["id"], "name": d.get("name_by_user") or d.get("name") or "",
                             "manufacturer": d.get("manufacturer") or "", "model": d.get("model") or "",
                             "model_id": d.get("model_id") or "", "sw_version": d.get("sw_version") or "",
                             "hw_version": d.get("hw_version") or "", "area_id": d.get("area_id"),
                             "integration": integration, "via_device_id": d.get("via_device_id"),
                             "entry_type": d.get("entry_type") or "", "disabled": 1 if d.get("disabled_by") else 0,
                             "connections": d.get("connections") or [], "identifiers": d.get("identifiers") or [],
                             "entities": [], "protocol": "unknown", "matter": 0, "updated": time.time()}
        ents = {}
        for e in entities or []:
            eid = e["entity_id"]
            ext = extended.get(eid) or {}
            dev = devs.get(e.get("device_id"))
            domain = eid.split(".", 1)[0]
            st = self.states.get(eid, {})
            attrs = st.get("attrs", {})
            ent = {"entity_id": eid, "device_id": e.get("device_id"), "domain": domain,
                   "area_id": e.get("area_id") or (dev or {}).get("area_id"),
                   "name": attrs.get("friendly_name") or e.get("name") or e.get("original_name") or eid,
                   "platform": e.get("platform") or "",
                   "device_class": attrs.get("device_class") or ext.get("device_class") or ext.get("original_device_class") or "",
                   "category": e.get("entity_category") or "", "hidden": 1 if e.get("hidden_by") else 0,
                   "disabled": 1 if e.get("disabled_by") else 0, "aliases": list(ext.get("aliases") or []),
                   "original_name": e.get("original_name") or ""}
            ents[eid] = ent
            if dev:
                dev["entities"].append(eid)
        for eid, st in self.states.items():
            if eid not in ents:
                ents[eid] = {"entity_id": eid, "device_id": None, "domain": eid.split(".", 1)[0], "area_id": None,
                             "name": st["attrs"].get("friendly_name") or eid, "platform": "",
                             "device_class": st["attrs"].get("device_class", ""), "category": "", "hidden": 0,
                             "disabled": 0, "aliases": [], "original_name": ""}
        for ent in ents.values():
            attrs = self.states.get(ent["entity_id"], {}).get("attrs", {})
            ent["capabilities"] = sorted(capabilities(ent["domain"], attrs))
            ent["controllable"] = int(ent["domain"] in DOMAIN_PRIORITY and not ent["category"] and not ent["hidden"]
                                      and not ent["disabled"] and ent["entity_id"] in self.states)
        for dev in devs.values():
            names = [(ents[x].get("original_name") or ents[x]["name"]).lower() for x in dev["entities"] if x in ents]
            dev["protocol"], dev["matter"] = self._protocol(dev, names, devs)
        self.devices, self.entities = devs, ents
        self._init_motion()
        self._rebuild_catalog()
        self.synced_at = time.time()
        self.rev += 1
        store.touch()

    def _protocol(self, dev: dict, entity_names: list[str], devs: dict) -> tuple[str, int]:
        integ = dev["integration"]
        ids = [(str(i[0]), str(i[1]).lower()) for i in dev["identifiers"] if len(i) >= 2]
        conns = {str(c[0]) for c in dev["connections"] if c}
        text = f"{dev['manufacturer']} {dev['model']} {dev['model_id']}".lower()
        matter = integ == "matter" or any(i[0] == "matter" for i in ids)
        if dev["entry_type"] == "service" or integ in VIRTUAL_INT:
            return "virtual", 0
        if matter:
            net = self.matter_net.get(dev["device_id"])
            if net in ("thread", "wifi", "ethernet"):
                return net, 1
            if any("thread" in n for n in entity_names):
                return "thread", 1
            return ("wifi" if "mac" in conns else "matter"), 1
        if integ == "homekit_controller":
            if any("thread" in n for n in entity_names):
                return "thread", 0
            return ("bluetooth" if "bluetooth" in conns else "wifi"), 0
        if "zigbee" in conns or (integ in ZIGBEE_INT and integ not in ZIGBEE_HUBS):
            return "zigbee", 0
        if integ in ZIGBEE_HUBS:
            return ("zigbee" if dev["via_device_id"] else "ethernet"), 0
        if integ == "mqtt":
            via = devs.get(dev["via_device_id"]) or {}
            if any("zigbee2mqtt" in i[1] for i in ids) or "zigbee2mqtt" in f"{text} {via.get('model', '')} " \
                                                                            f"{via.get('manufacturer', '')}".lower():
                return "zigbee", 0
            if "tasmota" in text or "esp" in text or "shelly" in text:
                return "wifi", 0
            return "mqtt", 0
        if integ in ZWAVE_INT:
            return "zwave", 0
        if "bluetooth" in conns or integ in BT_INT:
            return "bluetooth", 0
        if integ in WIFI_INT:
            return "wifi", 0
        if integ in LAN_INT:
            return "lan", 0
        if integ == "mobile_app":
            return "app", 0
        if integ in CLOUD_INT:
            return "cloud", 0
        for word, proto in (("zigbee", "zigbee"), ("thread", "thread"), ("z-wave", "zwave"), ("wi-fi", "wifi"),
                            ("wifi", "wifi"), ("bluetooth", "bluetooth")):
            if word in text:
                return proto, 0
        if "mac" in conns:
            return "lan", 0
        return "unknown", 0

    async def _matter_diagnostics(self) -> None:
        changed = False
        for dev in list(self.devices.values()):
            if not dev["matter"] or dev["device_id"] in self.matter_net:
                continue
            try:
                diag = await self._call({"type": "matter/node_diagnostics", "device_id": dev["device_id"]}, 10) or {}
            except (HAError, asyncio.TimeoutError):
                continue
            net = str(diag.get("network_type") or "").lower()
            if net in ("thread", "wifi", "ethernet"):
                self.matter_net[dev["device_id"]] = net
                dev["protocol"] = net
                changed = True
        if changed:
            self.db.set_meta("matter_net", self.matter_net)
            await asyncio.to_thread(self._persist_registries)
            self.rev += 1
            store.touch()

    def _persist_registries(self) -> None:
        def write(c):
            for table in ("floors", "areas", "devices", "entities", "states"):
                c.execute(f"DELETE FROM {table}")
            c.executemany("INSERT INTO floors VALUES (?,?,?,?)",
                          [(f["floor_id"], f["name"], f["level"], json.dumps(f["aliases"])) for f in self.floors.values()])
            c.executemany("INSERT INTO areas VALUES (?,?,?,?,?)",
                          [(a["area_id"], a["name"], a["floor_id"], json.dumps(a["aliases"]), a["icon"])
                           for a in self.areas.values()])
            c.executemany("INSERT INTO devices VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          [(d["device_id"], d["name"], d["manufacturer"], d["model"], d["model_id"], d["sw_version"],
                            d["hw_version"], d["area_id"], d["integration"], d["protocol"], d["matter"],
                            d["via_device_id"], d["entry_type"], d["disabled"], json.dumps(d["connections"]),
                            json.dumps(d["identifiers"]), d["updated"]) for d in self.devices.values()])
            c.executemany("INSERT INTO entities VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          [(e["entity_id"], e["device_id"], e["area_id"], e["domain"], e["name"], e["platform"],
                            e["device_class"], e["category"], e["hidden"], e["disabled"], json.dumps(e["aliases"]),
                            json.dumps(e["capabilities"]), e["controllable"]) for e in self.entities.values()])
            now = time.time()
            c.executemany("INSERT INTO states VALUES (?,?,?,?,?)",
                          [(k, v["state"], json.dumps(v["attrs"], default=str), v["lc"], now)
                           for k, v in self.states.items()])
            c.execute("INSERT OR REPLACE INTO meta VALUES ('synced_at', ?)", (json.dumps(self.synced_at),))
            c.execute("INSERT OR REPLACE INTO meta VALUES ('ha_version', ?)", (json.dumps(self.ha_version),))
        self.db.run(write)

    def _rebuild_catalog(self) -> None:
        all_names = [a["name"] for a in self.areas.values()]
        cat = Catalog()
        for aid, a in self.areas.items():
            cat.areas[aid] = {"name": a["name"], "floor_id": a.get("floor_id"),
                              "names": area_names(a["name"], a["aliases"] + self.aliases.get(f"area:{aid}", []), all_names)}
        for fid, f in self.floors.items():
            cat.floors[fid] = {"name": f["name"], "level": f.get("level"),
                               "names": [p for p in {phrase_stems(f["name"])} | {phrase_stems(x) for x in f["aliases"]} if p]}
        light_words = DOMAIN_PHRASES["light"]
        area_entities: dict = {}
        for eid, e in self.entities.items():
            if e.get("area_id"):
                area_entities.setdefault(e["area_id"], []).append(eid)
            if not e.get("controllable"):
                continue
            st = self.states.get(eid, {})
            names = {e["name"]} | set(e["aliases"]) | set(self.aliases.get(f"entity:{eid}", []))
            dev = self.devices.get(e["device_id"] or "")
            if dev and (not e.get("original_name") or e["name"] == dev["name"]):
                names.add(dev["name"])
            phrases = [p for p in {phrase_stems(n) for n in names if n} if p]
            cat.entities[eid] = {
                "entity_id": eid, "domain": e["domain"], "name": e["name"], "area_id": e.get("area_id"),
                "device_id": e.get("device_id"), "device_class": e.get("device_class", ""), "controllable": True,
                "names": phrases, "caps": set(e.get("capabilities") or []), "state": st.get("state"),
                "attrs": st.get("attrs", {}), "is_group": isinstance(st.get("attrs", {}).get("entity_id"), list),
                "as_light": e["domain"] == "switch" and any(find_phrase(list(p), lw) >= 0
                                                            for p in phrases for lw in light_words)}
        room = self.settings()["room"]
        cat.default_area = next((aid for aid, a in self.areas.items()
                                 if room and norm(a["name"]) == norm(room)), None)
        cat.occupied = list(self.occupied)
        self.area_entities = area_entities
        self.catalog = cat
