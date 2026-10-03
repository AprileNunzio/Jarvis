from dataclasses import dataclass, field
from typing import Dict, List, Optional

from server.core.kernel.domain.dag import ExecutionDag
from server.core.kernel.domain.node import TERMINAL_STATES, NodeState
from server.core.kernel.domain.outcome import ErrorPayload, NodeResult


@dataclass
class NodeRun:
    state: NodeState = NodeState.PENDING
    attempts: int = 0
    result: Optional[NodeResult] = None
    error: Optional[ErrorPayload] = None
    history: List[NodeState] = field(default_factory=list)
    last_attempt: Optional[NodeResult] = None
    episode_ids: List[str] = field(default_factory=list)

    def move(self, state: NodeState) -> None:
        self.state = state
        self.history.append(state)


class DagRun:
    def __init__(self, dag: ExecutionDag) -> None:
        self.dag = dag
        self.nodes: Dict[str, NodeRun] = {node_id: NodeRun() for node_id in dag.nodes}

    def state_of(self, node_id: str) -> NodeState:
        return self.nodes[node_id].state

    def accepted_results(self) -> Dict[str, NodeResult]:
        return {n: r.result for n, r in self.nodes.items() if r.state is NodeState.ACCEPTED and r.result}

    def completed_count(self) -> int:
        return sum(1 for r in self.nodes.values() if r.state in TERMINAL_STATES)

    def is_finished(self) -> bool:
        return all(r.state in TERMINAL_STATES for r in self.nodes.values())

    def succeeded(self) -> bool:
        return all(r.state is NodeState.ACCEPTED for r in self.nodes.values())

    def invalidate(self, node_id: str) -> frozenset:
        affected = {node_id} | self.dag.dependents_of(node_id)
        for target in affected:
            self.nodes[target] = NodeRun()
        return frozenset(affected)
