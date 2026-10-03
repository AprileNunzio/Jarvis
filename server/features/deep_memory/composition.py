import os
import sqlite3
import threading

from server.config.env import settings
from server.core.cognitive_audit.embedding_engine import embedding_engine
from server.features.deep_memory.application.failure_index import FailureIndex
from server.features.deep_memory.application.workspace import StructureWorkspace
from server.features.deep_memory.infrastructure.sqlite_episodes import SqliteEpisodeStore
from server.features.deep_memory.infrastructure.sqlite_structure import SqliteDerivedCache, SqliteStructureStore


class DeepMemory:
    def __init__(self, db_path: str) -> None:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        connection = sqlite3.connect(db_path, check_same_thread=False)
        connection.execute("PRAGMA journal_mode=WAL")
        lock = threading.Lock()
        self._structure = SqliteStructureStore(connection, lock)
        self._cache = SqliteDerivedCache(connection, lock)
        self.failures = FailureIndex(SqliteEpisodeStore(connection, lock), semantic=embedding_engine)

    def workspace(self, project_id: str) -> StructureWorkspace:
        return StructureWorkspace(project_id, self._structure, self._cache)


deep_memory = DeepMemory(os.path.join(settings.DATA_DIR, "db", "deep_memory.sqlite"))
