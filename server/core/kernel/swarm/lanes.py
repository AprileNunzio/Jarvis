import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import AsyncIterator, Dict, Tuple

from server.core.kernel.domain.node import NodeKind


class Lane(str, Enum):
    ANALYTIC = "analytic"
    CODING = "coding"
    PARAMETRIC = "parametric"
    ACTUATION = "actuation"


@dataclass(frozen=True)
class LaneSpec:
    lane: Lane
    agent_ids: Tuple[str, ...]
    concurrency: int


LANES: Tuple[LaneSpec, ...] = (
    LaneSpec(Lane.ANALYTIC, ("analytic_reasoner",), 2),
    LaneSpec(Lane.CODING, ("agent_self_healing_coder",), 1),
    LaneSpec(Lane.PARAMETRIC, ("parametric_designer",), 1),
    LaneSpec(Lane.ACTUATION, (), 2),
)

LANE_BY_KIND: Dict[NodeKind, Lane] = {
    NodeKind.REASONING: Lane.ANALYTIC,
    NodeKind.CODE: Lane.CODING,
    NodeKind.TOOL_SYNTHESIS: Lane.CODING,
    NodeKind.PARAMETRIC: Lane.PARAMETRIC,
    NodeKind.RPA: Lane.ACTUATION,
    NodeKind.DESTRUCTIVE_IO: Lane.ACTUATION,
}


def lane_for(kind: NodeKind) -> Lane:
    return LANE_BY_KIND[kind]


class LaneGovernor:
    def __init__(self, specs: Tuple[LaneSpec, ...] = LANES) -> None:
        self._specs: Dict[Lane, LaneSpec] = {s.lane: s for s in specs}
        self._slots: Dict[Lane, asyncio.Semaphore] = {s.lane: asyncio.Semaphore(s.concurrency) for s in specs}

    def spec(self, lane: Lane) -> LaneSpec:
        return self._specs[lane]

    @asynccontextmanager
    async def slot(self, lane: Lane) -> AsyncIterator[None]:
        async with self._slots[lane]:
            yield
