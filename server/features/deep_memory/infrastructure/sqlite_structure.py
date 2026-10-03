import json
import sqlite3
import threading
from typing import Any, Dict, Optional, Sequence

from server.features.deep_memory.domain.structure import FileParse, ImportRef, RawRefs, Symbol


def _encode(parse: FileParse) -> str:
    return json.dumps({
        "fingerprint": parse.fingerprint,
        "symbols": [[s.symbol_id, s.kind, s.name, s.fingerprint] for s in parse.symbols],
        "refs": {k: [sorted(r.names), sorted(map(list, r.attributes))] for k, r in parse.refs.items()},
        "imports": [[i.alias, i.module, i.member, i.level] for i in parse.imports],
        "deps": sorted(parse.direct_dependencies),
    })


def _decode(path: str, payload: str) -> FileParse:
    data = json.loads(payload)
    return FileParse(
        path=path,
        fingerprint=data["fingerprint"],
        symbols=tuple(Symbol(*s) for s in data["symbols"]),
        refs={k: RawRefs(frozenset(v[0]), frozenset(tuple(a) for a in v[1])) for k, v in data["refs"].items()},
        imports=tuple(ImportRef(*i) for i in data["imports"]),
        direct_dependencies=frozenset(data["deps"]),
    )


class SqliteStructureStore:
    def __init__(self, connection: sqlite3.Connection, lock: threading.Lock) -> None:
        self._db = connection
        self._lock = lock
        with self._lock:
            self._db.executescript("""
                CREATE TABLE IF NOT EXISTS structure_files (
                    project_id TEXT NOT NULL, path TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY (project_id, path));
            """)
            self._db.commit()

    def load(self, project_id: str) -> Dict[str, FileParse]:
        with self._lock:
            rows = self._db.execute("SELECT path, payload FROM structure_files WHERE project_id = ?", (project_id,)).fetchall()
        return {path: _decode(path, payload) for path, payload in rows}

    def save(self, project_id: str, parse: FileParse) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO structure_files VALUES (?, ?, ?)", (project_id, parse.path, _encode(parse)))
            self._db.commit()

    def delete(self, project_id: str, path: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM structure_files WHERE project_id = ? AND path = ?", (project_id, path))
            self._db.commit()


class SqliteDerivedCache:
    def __init__(self, connection: sqlite3.Connection, lock: threading.Lock) -> None:
        self._db = connection
        self._lock = lock
        with self._lock:
            self._db.executescript("""
                CREATE TABLE IF NOT EXISTS derived_cache (
                    project_id TEXT NOT NULL, symbol_id TEXT NOT NULL, cache_key TEXT NOT NULL,
                    value TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    PRIMARY KEY (project_id, symbol_id, cache_key));
            """)
            self._db.commit()

    def get(self, project_id: str, symbol_id: str, key: str) -> Optional[Any]:
        with self._lock:
            row = self._db.execute(
                "SELECT value FROM derived_cache WHERE project_id = ? AND symbol_id = ? AND cache_key = ?",
                (project_id, symbol_id, key),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, project_id: str, symbol_id: str, key: str, value: Any, fingerprint: str) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO derived_cache VALUES (?, ?, ?, ?, ?)",
                (project_id, symbol_id, key, json.dumps(value, default=str), fingerprint),
            )
            self._db.commit()

    def drop(self, project_id: str, symbol_ids: Sequence[str]) -> int:
        dropped = 0
        with self._lock:
            for start in range(0, len(symbol_ids), 400):
                chunk = symbol_ids[start : start + 400]
                marks = ",".join("?" * len(chunk))
                dropped += self._db.execute(
                    f"DELETE FROM derived_cache WHERE project_id = ? AND symbol_id IN ({marks})", (project_id, *chunk)
                ).rowcount
            self._db.commit()
        return dropped
