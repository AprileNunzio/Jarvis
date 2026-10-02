import asyncio
import json
import sqlite3

from config import DEMO, read_env
from features.home_assistant.answers import HomeAnswers
from features.home_assistant.commands import HomeCommands
from features.home_assistant.connection import HomeConnection
from features.home_assistant.constants import log
from features.home_assistant.db import HomeDB
from features.home_assistant.live import HomeLive
from features.home_assistant.nlu.matching import Catalog
from features.home_assistant.registry import HomeRegistry
from features.home_assistant.reports import HomeReports


class HomeBrain(HomeConnection, HomeRegistry, HomeLive, HomeCommands, HomeAnswers, HomeReports):
    def __init__(self) -> None:
        self.db = HomeDB()
        self.status = "starting"
        self.error = ""
        self.ha_version = ""
        self.ha_name = ""
        self.url = ""
        self.connected_at = 0.0
        self.synced_at = 0.0
        self.sync_ms = 0
        self.rev = 0
        self.floors: dict = {}
        self.areas: dict = {}
        self.devices: dict = {}
        self.entities: dict = {}
        self.states: dict = {}
        self.services: dict = {}
        self.area_entities: dict = {}
        self.catalog = Catalog()
        self.aliases: dict = {k: json.loads(v) for k, v in self.db.query("SELECT target, names FROM aliases")}
        self.learned: dict = {k: json.loads(v) for k, v in self.db.query("SELECT text, plan FROM learned")}
        self.matter_net: dict = self.db.meta("matter_net", {}) or {}
        self.last_motion: dict = {}
        self.occupied: list = []
        self.pending: dict | None = None
        self.stats = {"commands": 0, "avg_ms": 0, "llm": 0, "learned_hits": 0}
        self._ws = None
        self._id = 0
        self._futures: dict = {}
        self._dirty_states: dict = {}
        self._activity: list = []
        self._resync: asyncio.Task | None = None
        self._creds = ("", "")
        self._load_from_db()

    @staticmethod
    def settings() -> dict:
        env = read_env()
        return {"url": env.get("HOME_ASSISTANT_URL", "").strip().rstrip("/"),
                "token": env.get("HOME_ASSISTANT_TOKEN", "").strip(),
                "enabled": env.get("JARVIS_HOME_ASSISTANT", "1") != "0",
                "room": env.get("JARVIS_HOME_ROOM", "").strip(),
                "motion_min": float(env.get("JARVIS_HOME_MOTION_MIN", "5") or 5),
                "confirm": env.get("JARVIS_HOME_CONFIRM", "1") != "0",
                "verify_ssl": env.get("HOME_ASSISTANT_VERIFY_SSL", "1") != "0"}

    @property
    def online(self) -> bool:
        return self.status == "online" or (DEMO and bool(self.entities))

    def _load_from_db(self) -> None:
        try:
            q = self.db.query
            self.floors = {r[0]: {"floor_id": r[0], "name": r[1], "level": r[2], "aliases": json.loads(r[3] or "[]")}
                           for r in q("SELECT * FROM floors")}
            self.areas = {r[0]: {"area_id": r[0], "name": r[1], "floor_id": r[2], "aliases": json.loads(r[3] or "[]"),
                                 "icon": r[4]} for r in q("SELECT * FROM areas")}
            cols = [d[1] for d in self.db.conn.execute("PRAGMA table_info(devices)").fetchall()]
            for r in q("SELECT * FROM devices"):
                d = dict(zip(cols, r))
                d["connections"], d["identifiers"] = json.loads(d["connections"] or "[]"), json.loads(d["identifiers"] or "[]")
                d["entities"] = []
                self.devices[d["device_id"]] = d
            cols = [d[1] for d in self.db.conn.execute("PRAGMA table_info(entities)").fetchall()]
            for r in q("SELECT * FROM entities"):
                e = dict(zip(cols, r))
                e["aliases"] = json.loads(e["aliases"] or "[]")
                e["capabilities"] = json.loads(e["capabilities"] or "[]")
                self.entities[e["entity_id"]] = e
                if e["device_id"] in self.devices:
                    self.devices[e["device_id"]]["entities"].append(e["entity_id"])
            self.states = {r[0]: {"state": r[1], "attrs": json.loads(r[2] or "{}"), "lc": r[3]}
                           for r in q("SELECT entity_id, state, attributes, last_changed FROM states")}
            self.synced_at = float(self.db.meta("synced_at", 0) or 0)
            self.ha_version = self.db.meta("ha_version", "") or ""
            self._rebuild_catalog()
        except (sqlite3.Error, ValueError) as exc:
            log.warning("Copia locale della casa non leggibile: %s", exc)


brain = HomeBrain()
