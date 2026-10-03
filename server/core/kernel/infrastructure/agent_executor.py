from typing import Mapping, Optional

from server.core.agent_registry.interfaces import AgentTaskRequest
from server.core.agent_registry.pool_manager import AgentPoolManager
from server.core.kernel.domain.node import NodeSpec
from server.core.kernel.domain.outcome import ErrorPayload, NodeResult


class AgentPoolExecutor:
    def __init__(self, pool: AgentPoolManager, user_id: str, device_id: str, goal: str) -> None:
        self._pool = pool
        self._user_id = user_id
        self._device_id = device_id
        self._goal = goal

    async def execute(
        self,
        node: NodeSpec,
        upstream: Mapping[str, NodeResult],
        feedback: Optional[ErrorPayload],
    ) -> NodeResult:
        request = AgentTaskRequest(
            task_id=f"plan_{node.node_id}",
            user_id=self._user_id,
            intent=node.intent,
            raw_query=self._query(node, feedback),
            parameters={
                "device_id": self._device_id,
                "plan_context": self._goal,
                "previous_results": {n: r.output for n, r in upstream.items()},
                "previous_error": feedback.to_prompt() if feedback else "",
            },
        )
        agent = await self._pool.select_best_agent(request)
        response = await agent.execute(request)
        return NodeResult(
            node_id=node.node_id,
            output={**response.result_data, "status": response.status},
            speech=response.speech_output,
            agent_id=response.agent_id,
        )

    @staticmethod
    def _query(node: NodeSpec, feedback: Optional[ErrorPayload]) -> str:
        if feedback is None:
            return node.description
        return f"{node.description}\n\nIl tentativo precedente è fallito: {feedback.to_prompt()}\nCorreggi e riprova."
