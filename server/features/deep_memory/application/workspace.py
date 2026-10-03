from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Optional

from server.features.deep_memory.application.ports import DerivedCache, StructureStore
from server.features.deep_memory.domain.python_extractor import SourceError, extract_python
from server.features.deep_memory.domain.resolver import build_graph
from server.features.deep_memory.domain.script_extractor import extract_script, is_script
from server.features.deep_memory.domain.structure import ChangeSet, FileParse, StructureGraph, diff_symbols


@dataclass(frozen=True)
class Invalidation:
    changes: ChangeSet
    invalidated: FrozenSet[str]
    dropped_cache_entries: int

    @property
    def changed(self) -> FrozenSet[str]:
        return self.changes.touched


class StructureWorkspace:
    def __init__(self, project_id: str, store: StructureStore, cache: DerivedCache) -> None:
        self._project = project_id
        self._store = store
        self._cache = cache
        self._parses: Dict[str, FileParse] = store.load(project_id)
        self._graph: StructureGraph = build_graph(self._parses.values())

    @property
    def graph(self) -> StructureGraph:
        return self._graph

    def update_file(self, path: str, source: str) -> Invalidation:
        parse = self._parse(path, source)
        previous = self._parses.get(path)
        if previous is not None and previous.fingerprint == parse.fingerprint:
            return Invalidation(ChangeSet(), frozenset(), 0)
        self._store.save(self._project, parse)
        return self._apply({**self._parses, path: parse})

    def remove_file(self, path: str) -> Invalidation:
        if path not in self._parses:
            return Invalidation(ChangeSet(), frozenset(), 0)
        self._store.delete(self._project, path)
        remaining = {p: f for p, f in self._parses.items() if p != path}
        return self._apply(remaining)

    def remember(self, symbol_id: str, key: str, value: Any) -> None:
        symbol = self._graph.symbols.get(symbol_id)
        if symbol is None:
            raise KeyError(f"unknown symbol {symbol_id}")
        self._cache.put(self._project, symbol_id, key, value, symbol.fingerprint)

    def recall(self, symbol_id: str, key: str) -> Optional[Any]:
        return self._cache.get(self._project, symbol_id, key)

    def _apply(self, parses: Dict[str, FileParse]) -> Invalidation:
        old_graph = self._graph
        new_graph = build_graph(parses.values())
        changes = diff_symbols(old_graph.symbols, new_graph.symbols)
        affected = changes.touched | old_graph.dependents_of(changes.touched) | new_graph.dependents_of(changes.touched)
        dropped = self._cache.drop(self._project, sorted(affected))
        self._parses, self._graph = parses, new_graph
        return Invalidation(changes, frozenset(affected), dropped)

    @staticmethod
    def _parse(path: str, source: str) -> FileParse:
        if path.endswith(".py"):
            return extract_python(path, source)
        if is_script(path):
            return extract_script(path, source)
        raise SourceError(f"{path}: unsupported file type")
