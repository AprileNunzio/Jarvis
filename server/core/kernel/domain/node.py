from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Tuple


class NodeKind(str, Enum):
    REASONING = "reasoning"
    CODE = "code"
    TOOL_SYNTHESIS = "tool_synthesis"
    PARAMETRIC = "parametric"
    RPA = "rpa"
    DESTRUCTIVE_IO = "destructive_io"


class RiskLevel(IntEnum):
    READ_ONLY = 0
    REVERSIBLE = 1
    DESTRUCTIVE = 2


class NodeState(str, Enum):
    PENDING = "pending"
    BLOCKED_ON_CONSENSUS = "blocked_on_consensus"
    READY = "ready"
    RUNNING = "running"
    VALIDATING = "validating"
    HEALING = "healing"
    ACCEPTED = "accepted"
    FAILED = "failed"
    SKIPPED = "skipped"
    REJECTED = "rejected"


TERMINAL_STATES = frozenset({NodeState.ACCEPTED, NodeState.FAILED, NodeState.SKIPPED, NodeState.REJECTED})


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    deadline_seconds: float = 300.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.deadline_seconds <= 0:
            raise ValueError("invalid retry policy")


@dataclass(frozen=True)
class NodeSpec:
    node_id: str
    kind: NodeKind
    description: str
    depends_on: Tuple[str, ...] = ()
    risk: RiskLevel = RiskLevel.READ_ONLY
    validator_id: str = "default"
    intent: str = "GENERAL_INTELLIGENCE"
    retry: RetryPolicy = RetryPolicy()
