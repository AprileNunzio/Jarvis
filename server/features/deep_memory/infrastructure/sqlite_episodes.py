import sqlite3
import threading
from typing import List, Optional, Tuple

from server.features.deep_memory.domain.episodes import Episode, pack, unpack


class SqliteEpisodeStore:
    def __init__(self, connection: sqlite3.Connection, lock: threading.Lock) -> None:
        self._db = connection
        self._lock = lock
        with self._lock:
            self._db.executescript("""
                CREATE TABLE IF NOT EXISTS failure_episodes (
                    episode_id TEXT PRIMARY KEY, goal TEXT NOT NULL, approach TEXT NOT NULL,
                    error_kind TEXT NOT NULL, error_message TEXT NOT NULL, created_at REAL NOT NULL,
                    resolution TEXT NOT NULL DEFAULT '', semantic BLOB, lexical BLOB NOT NULL);
            """)
            self._db.commit()

    def add(self, episode: Episode, semantic: Optional[List[float]], lexical: List[float]) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO failure_episodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (episode.episode_id, episode.goal, episode.approach, episode.error_kind, episode.error_message,
                 episode.created_at, episode.resolution, pack(semantic) if semantic else None, pack(lexical)),
            )
            self._db.commit()

    def all_vectors(self) -> List[Tuple[Episode, Optional[List[float]], List[float]]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT episode_id, goal, approach, error_kind, error_message, created_at, resolution, semantic, lexical "
                "FROM failure_episodes ORDER BY created_at DESC LIMIT 2000"
            ).fetchall()
        return [(Episode(*row[:7]), unpack(row[7]) if row[7] else None, unpack(row[8])) for row in rows]

    def mark_resolved(self, episode_id: str, resolution: str) -> bool:
        with self._lock:
            changed = self._db.execute(
                "UPDATE failure_episodes SET resolution = ? WHERE episode_id = ?", (resolution, episode_id)
            ).rowcount
            self._db.commit()
        return changed > 0
