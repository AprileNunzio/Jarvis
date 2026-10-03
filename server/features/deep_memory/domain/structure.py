from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, Mapping, Set, Tuple

MODULE_KIND = "module"


@dataclass(frozen=True)
class Symbol:
    symbol_id: str
    kind: str
    name: str
    fingerprint: str


@dataclass(frozen=True)
class RawRefs:
    names: FrozenSet[str] = frozenset()
    attributes: FrozenSet[Tuple[str, str]] = frozenset()


@dataclass(frozen=True)
class ImportRef:
    alias: str
    module: str
    member: str = ""
    level: int = 0


@dataclass(frozen=True)
class FileParse:
    path: str
    fingerprint: str
    symbols: Tuple[Symbol, ...]
    refs: Mapping[str, RawRefs] = field(default_factory=dict)
    imports: Tuple[ImportRef, ...] = ()
    direct_dependencies: FrozenSet[str] = frozenset()


@dataclass(frozen=True)
class ChangeSet:
    added: FrozenSet[str] = frozenset()
    removed: FrozenSet[str] = frozenset()
    modified: FrozenSet[str] = frozenset()

    @property
    def touched(self) -> FrozenSet[str]:
        return self.added | self.removed | self.modified


@dataclass(frozen=True)
class StructureGraph:
    symbols: Mapping[str, Symbol]
    edges: FrozenSet[Tuple[str, str]]

    def dependents_of(self, symbol_ids: Iterable[str]) -> FrozenSet[str]:
        reverse: Dict[str, Set[str]] = {}
        for source, target in self.edges:
            reverse.setdefault(target, set()).add(source)
        found: Set[str] = set()
        frontier = list(symbol_ids)
        while frontier:
            current = frontier.pop()
            for dependent in reverse.get(current, ()):
                if dependent not in found:
                    found.add(dependent)
                    frontier.append(dependent)
        return frozenset(found)

    def dependencies_of(self, symbol_id: str) -> FrozenSet[str]:
        return frozenset(t for s, t in self.edges if s == symbol_id)


def diff_symbols(old: Mapping[str, Symbol], new: Mapping[str, Symbol]) -> ChangeSet:
    added = frozenset(new.keys() - old.keys())
    removed = frozenset(old.keys() - new.keys())
    modified = frozenset(k for k in new.keys() & old.keys() if new[k].fingerprint != old[k].fingerprint)
    return ChangeSet(added, removed, modified)
