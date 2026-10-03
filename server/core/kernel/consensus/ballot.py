from dataclasses import dataclass
from typing import Protocol

from server.core.kernel.domain.dag import ExecutionDag


@dataclass(frozen=True)
class Ballot:
    voter: str
    approve: bool
    reason: str


class Voter(Protocol):
    name: str
    can_veto: bool

    async def vote(self, dag: ExecutionDag) -> Ballot: ...


def describe_dag(dag: ExecutionDag) -> str:
    lines = []
    for node_id in sorted(dag.nodes):
        spec = dag.nodes[node_id]
        deps = ",".join(spec.depends_on) or "-"
        lines.append(f"- {node_id} [{spec.kind.value}, rischio {spec.risk.name}, dipende da {deps}]: {spec.description}")
    return "\n".join(lines)
