from typing import Mapping, Optional

from server.core.agent_registry.interfaces import AgentTaskRequest, BaseAgent
from server.core.agent_registry.pool_manager import AgentPoolManager
from server.core.kernel.domain.node import NodeSpec
from server.core.kernel.domain.outcome import ErrorPayload, NodeResult
from server.core.kernel.swarm.lanes import LaneGovernor, LaneSpec, lane_for
from server.core.orchestrator.brain_routing import preferred_brain_for


class SwarmBroker:
    def __init__(self, pool: AgentPoolManager, governor: LaneGovernor, user_id: str, device_id: str, goal: str) -> None:
        self._pool = pool
        self._governor = governor
        self._user_id = user_id
        self._device_id = device_id
        self._goal = goal

    async def execute(
        self,
        node: NodeSpec,
        upstream: Mapping[str, NodeResult],
        feedback: Optional[ErrorPayload],
    ) -> NodeResult:
        lane = lane_for(node.kind)
        spec = self._governor.spec(lane)
        request = self._request(node, upstream, feedback)
        async with self._governor.slot(lane):
            agent = await self._select(request, spec)
            request.preferred_brain = preferred_brain_for(agent.agent_id)
            response = await agent.execute(request)
        return NodeResult(
            node_id=node.node_id,
            output={**response.result_data, "status": response.status},
            speech=response.speech_output,
            agent_id=response.agent_id,
        )

    async def _select(self, request: AgentTaskRequest, spec: LaneSpec) -> BaseAgent:
        if self._pool.registered(spec.agent_ids):
            return self._pool.select_among(request, spec.agent_ids)
        return await self._pool.select_best_agent(request)

    def _request(self, node: NodeSpec, upstream: Mapping[str, NodeResult], feedback: Optional[ErrorPayload]) -> AgentTaskRequest:
        return AgentTaskRequest(
            task_id=f"plan_{node.node_id}",
            user_id=self._user_id,
            intent=node.intent,
            raw_query=self._query(node, feedback),
            parameters={
                "device_id": self._device_id,
                "plan_context": self._goal,
                "node_kind": node.kind.value,
                "previous_results": {n: {**r.output, "speech": r.speech} for n, r in upstream.items()},
                "previous_error": feedback.to_prompt() if feedback else "",
            },
        )

    @staticmethod
    def _query(node: NodeSpec, feedback: Optional[ErrorPayload]) -> str:
        if feedback is None:
            return node.description
        if feedback.kind == "memory_warning":
            return f"{node.description}\n\nEsperienza passata da tenere presente:\n{feedback.message}"
        return f"{node.description}\n\nIl tentativo precedente è fallito: {feedback.to_prompt()}\nCorreggi e riprova."
