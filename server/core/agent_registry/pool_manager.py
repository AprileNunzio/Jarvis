from typing import Dict, List, Optional
from server.core.agent_registry.interfaces import BaseAgent, AgentTaskRequest
from server.shared.errors.domain_errors import AgentExecutionException

class AgentPoolManager:
    def __init__(self) -> None:
        self._registry: Dict[str, BaseAgent] = {}

    def register_agent(self, agent: BaseAgent) -> None:
        self._registry[agent.agent_id] = agent

    def list_agents(self) -> List[str]:
        return list(self._registry.keys())

    async def select_best_agent(self, request: AgentTaskRequest) -> BaseAgent:
        best_agent: Optional[BaseAgent] = None
        highest_score: float = -1.0

        for agent in self._registry.values():
            score = await agent.can_handle(request)
            if score > highest_score:
                highest_score = score
                best_agent = agent

        if not best_agent or highest_score < 0.2:
            raise AgentExecutionException(
                agent_name="orchestrator",
                message=f"No specialized agent available capable of handling intent '{request.intent}'",
                details={"intent": request.intent, "highest_score": highest_score}
            )

        return best_agent

agent_pool = AgentPoolManager()
