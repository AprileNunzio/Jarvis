import hashlib
import json
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Mapping, Sequence, Set, Tuple

from server.core.kernel.domain.errors import DagError
from server.core.kernel.domain.node import NodeSpec, RiskLevel

MAX_NODES = 24


@dataclass(frozen=True)
class ExecutionDag:
    nodes: Mapping[str, NodeSpec]

    @classmethod
    def build(cls, specs: Sequence[NodeSpec]) -> "ExecutionDag":
        if not specs:
            raise DagError("a plan needs at least one node")
        if len(specs) > MAX_NODES:
            raise DagError(f"a plan can have at most {MAX_NODES} nodes")
        nodes: Dict[str, NodeSpec] = {}
        for spec in specs:
            if not spec.node_id or spec.node_id in nodes:
                raise DagError(f"duplicate or empty node id: {spec.node_id!r}")
            if not spec.description.strip():
                raise DagError(f"node {spec.node_id} has no description")
            nodes[spec.node_id] = spec
        dag = cls(nodes)
        dag._check_references()
        dag.waves()
        return dag

    def _check_references(self) -> None:
        for spec in self.nodes.values():
            for dep in spec.depends_on:
                if dep not in self.nodes:
                    raise DagError(f"node {spec.node_id} depends on unknown node {dep}")
                if dep == spec.node_id:
                    raise DagError(f"node {spec.node_id} depends on itself")

    def waves(self) -> Tuple[Tuple[str, ...], ...]:
        remaining: Dict[str, Set[str]] = {n: set(s.depends_on) for n, s in self.nodes.items()}
        waves: List[Tuple[str, ...]] = []
        while remaining:
            ready = sorted(n for n, deps in remaining.items() if not deps)
            if not ready:
                raise DagError(f"cycle detected among nodes: {sorted(remaining)}")
            waves.append(tuple(ready))
            for node in ready:
                del remaining[node]
            for deps in remaining.values():
                deps.difference_update(ready)
        return tuple(waves)

    def dependents_of(self, node_id: str) -> FrozenSet[str]:
        found: Set[str] = set()
        frontier = [node_id]
        while frontier:
            current = frontier.pop()
            for spec in self.nodes.values():
                if current in spec.depends_on and spec.node_id not in found:
                    found.add(spec.node_id)
                    frontier.append(spec.node_id)
        return frozenset(found)

    def max_risk(self) -> RiskLevel:
        return max(spec.risk for spec in self.nodes.values())

    def fingerprint(self) -> str:
        canonical = [
            [s.node_id, s.kind.value, s.description, sorted(s.depends_on), int(s.risk), s.validator_id]
            for s in sorted(self.nodes.values(), key=lambda s: s.node_id)
        ]
        return hashlib.sha256(json.dumps(canonical, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
