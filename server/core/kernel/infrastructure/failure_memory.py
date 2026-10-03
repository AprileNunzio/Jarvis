from typing import Sequence

from server.core.kernel.domain.node import NodeSpec
from server.core.kernel.domain.outcome import ErrorPayload
from server.features.deep_memory.application.failure_index import FailureIndex


class DeepMemoryFailureAdapter:
    def __init__(self, index: FailureIndex) -> None:
        self._index = index

    async def warnings_for(self, node: NodeSpec) -> Sequence[str]:
        return await self._index.warnings_for(node.description)

    async def record_failure(self, node: NodeSpec, approach: str, error: ErrorPayload) -> str:
        episode = await self._index.record(node.description, approach, error.kind, error.message)
        return episode.episode_id

    def record_resolution(self, episode_ids: Sequence[str], summary: str) -> None:
        for episode_id in episode_ids:
            self._index.resolve(episode_id, summary)
