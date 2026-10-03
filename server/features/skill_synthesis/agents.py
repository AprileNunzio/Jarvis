import time
from typing import Any, Dict, List

from server.core.agent_registry.interfaces import AgentTaskRequest, AgentTaskResponse, BaseAgent
from server.features.skill_synthesis.application.matcher import best_match
from server.features.skill_synthesis.application.ports import ToolStore
from server.features.skill_synthesis.application.runner import DynamicToolRunner
from server.features.skill_synthesis.application.synthesizer import ToolSynthesizer

_SCALARS = (str, int, float, bool)


def _payload(request: AgentTaskRequest) -> Dict[str, Any]:
    parameters = {k: v for k, v in request.parameters.items() if isinstance(v, _SCALARS) and k not in ("previous_error",)}
    return {"query": request.raw_query, **parameters}


def _reply(request: AgentTaskRequest, agent_id: str, started: float, status: str, data: dict, speech: str) -> AgentTaskResponse:
    return AgentTaskResponse(
        task_id=request.task_id,
        agent_id=agent_id,
        status=status,
        result_data=data,
        speech_output=speech,
        execution_time_ms=(time.time() - started) * 1000,
    )


class DynamicToolsAgent(BaseAgent):
    def __init__(self, store: ToolStore, runner: DynamicToolRunner) -> None:
        self._store = store
        self._runner = runner

    @property
    def agent_id(self) -> str:
        return "dynamic_tools"

    @property
    def capabilities(self) -> List[str]:
        return [f"tool:{t.name}" for t in self._store.all()]

    async def can_handle(self, request: AgentTaskRequest) -> float:
        return best_match(self._store.all(), request.raw_query)[1]

    async def execute(self, request: AgentTaskRequest) -> AgentTaskResponse:
        started = time.time()
        tool, _ = best_match(self._store.all(), request.raw_query)
        if tool is None:
            return _reply(request, self.agent_id, started, "ERROR", {"reason": "no matching tool"}, "")
        run = await self._runner.run(tool, _payload(request))
        if not run.ok:
            return _reply(request, self.agent_id, started, "ERROR", {"tool": tool.name, "reason": run.error, "egress_denied": list(run.denied_hosts)}, "")
        speech = str(run.data.get("summary") or run.data)[:600]
        return _reply(request, self.agent_id, started, "SUCCESS", {"tool": tool.name, "data": run.data}, speech)


class ToolBuilderAgent(BaseAgent):
    def __init__(self, synthesizer: ToolSynthesizer) -> None:
        self._synthesizer = synthesizer

    @property
    def agent_id(self) -> str:
        return "tool_builder"

    @property
    def capabilities(self) -> List[str]:
        return ["tool_synthesis", "api_integration", "sandboxed_scripts"]

    async def can_handle(self, request: AgentTaskRequest) -> float:
        return 0.95 if request.parameters.get("node_kind") == "tool_synthesis" else 0.0

    async def execute(self, request: AgentTaskRequest) -> AgentTaskResponse:
        started = time.time()
        context = {"plan_context": request.parameters.get("plan_context", "")}
        outcome = await self._synthesizer.synthesize(request.raw_query, context)
        if not outcome.ok:
            return _reply(request, self.agent_id, started, "ERROR", {"reason": outcome.message}, "")
        data = {"tool": outcome.tool.name, "code": outcome.tool.source, "data": outcome.run.data,
                "egress_hosts": list(outcome.tool.egress_hosts), "attempts": outcome.attempts}
        return _reply(request, self.agent_id, started, "SUCCESS", data, str(outcome.run.data.get("summary") or outcome.message)[:600])
