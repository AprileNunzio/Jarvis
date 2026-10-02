import json
import sqlite3
import threading

from features.home_assistant.constants import DB_FILE, HOME_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS floors (floor_id TEXT PRIMARY KEY, name TEXT, level INTEGER, aliases TEXT);
CREATE TABLE IF NOT EXISTS areas (area_id TEXT PRIMARY KEY, name TEXT, floor_id TEXT, aliases TEXT, icon TEXT);
CREATE TABLE IF NOT EXISTS devices (device_id TEXT PRIMARY KEY, name TEXT, manufacturer TEXT, model TEXT,
    model_id TEXT, sw_version TEXT, hw_version TEXT, area_id TEXT, integration TEXT, protocol TEXT, matter INTEGER,
    via_device_id TEXT, entry_type TEXT, disabled INTEGER, connections TEXT, identifiers TEXT, updated REAL);
CREATE TABLE IF NOT EXISTS entities (entity_id TEXT PRIMARY KEY, device_id TEXT, area_id TEXT, domain TEXT,
    name TEXT, platform TEXT, device_class TEXT, category TEXT, hidden INTEGER, disabled INTEGER, aliases TEXT,
    capabilities TEXT, controllable INTEGER);
CREATE TABLE IF NOT EXISTS states (entity_id TEXT PRIMARY KEY, state TEXT, attributes TEXT, last_changed REAL,
    updated REAL);
CREATE TABLE IF NOT EXISTS activity (ts REAL, area_id TEXT, entity_id TEXT, kind TEXT, state TEXT);
CREATE INDEX IF NOT EXISTS idx_activity_ts ON activity(ts);
CREATE INDEX IF NOT EXISTS idx_activity_area ON activity(area_id, kind, ts);
CREATE TABLE IF NOT EXISTS commands (ts REAL, text TEXT, plan TEXT, ok INTEGER, ms INTEGER, source TEXT);
CREATE TABLE IF NOT EXISTS learned (text TEXT PRIMARY KEY, plan TEXT, uses INTEGER, ts REAL);
CREATE TABLE IF NOT EXISTS aliases (target TEXT PRIMARY KEY, names TEXT);
CREATE INDEX IF NOT EXISTS idx_entities_area ON entities(area_id);
CREATE INDEX IF NOT EXISTS idx_devices_area ON devices(area_id);
"""


class HomeDB:
    def __init__(self) -> None:
        HOME_DIR.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(SCHEMA)

    def run(self, fn):
        with self.lock:
            self.conn.execute("BEGIN")
            try:
                out = fn(self.conn)
                self.conn.execute("COMMIT")
                return out
            except Exception:
                self.conn.execute("ROLLBACK")
                raise

    def query(self, sql: str, args: tuple = ()) -> list:
        with self.lock:
            return self.conn.execute(sql, args).fetchall()

    def meta(self, key: str, default=None):
        rows = self.query("SELECT value FROM meta WHERE key=?", (key,))
        try:
            return json.loads(rows[0][0]) if rows else default
        except ValueError:
            return default

    def set_meta(self, key: str, value) -> None:
        self.run(lambda c: c.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, json.dumps(value))))
