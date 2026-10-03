from typing import Mapping, Optional, Protocol

from server.core.kernel.domain.dag import ExecutionDag
from server.core.kernel.domain.node import NodeSpec, NodeState
from server.core.kernel.domain.outcome import ConsensusVerdict, ErrorPayload, NodeResult, Verdict


class NodeExecutor(Protocol):
    async def execute(
        self,
        node: NodeSpec,
        upstream: Mapping[str, NodeResult],
        feedback: Optional[ErrorPayload],
    ) -> NodeResult: ...


class NodeValidator(Protocol):
    async def judge(self, node: NodeSpec, result: NodeResult) -> Verdict: ...


class ValidatorRegistry(Protocol):
    def resolve(self, validator_id: str) -> NodeValidator: ...


class ConsensusPort(Protocol):
    async def vote(self, dag: ExecutionDag) -> ConsensusVerdict: ...


class RunObserver(Protocol):
    async def on_transition(self, node_id: str, state: NodeState, completed: int, total: int) -> None: ...


class Checkpoint(Protocol):
    async def wait_if_paused(self) -> None: ...
