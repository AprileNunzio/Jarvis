import time
from typing import List

from server.core.agent_registry.interfaces import AgentTaskRequest, AgentTaskResponse, BaseAgent
from server.core.orchestrator.brain_routing import brain_order_for
from server.features.parametric.application.translator import SpecTranslationError
from server.features.parametric.composition import UnavailableModelError, build_designer


class ParametricDesignerAgent(BaseAgent):
    def __init__(self) -> None:
        self._designer = build_designer(lambda: brain_order_for(self.agent_id))

    @property
    def agent_id(self) -> str:
        return "parametric_designer"

    @property
    def capabilities(self) -> List[str]:
        return ["cad_generation", "parametric_modeling", "obj_export", "dxf_export", "autolisp_export"]

    async def can_handle(self, request: AgentTaskRequest) -> float:
        if request.intent == "3D_GENERATION" or request.parameters.get("node_kind") == "parametric":
            return 0.95
        return 0.0

    async def execute(self, request: AgentTaskRequest) -> AgentTaskResponse:
        started = time.time()
        hint = request.parameters.get("previous_error") or None
        try:
            result = await self._designer.design(request.raw_query, request.task_id, hint)
        except (SpecTranslationError, UnavailableModelError) as exc:
            return self._reply(request, started, "ERROR", {"reason": str(exc)}, "")
        stats = {"vertices": result.rendered.vertices, "faces": result.rendered.faces, "parts": len(result.spec.parts),
                 "units": result.spec.units, "attempts": result.attempts}
        data = {"files": result.rendered.files, "paths": result.written, "stats": stats,
                "spec": result.spec.model_dump(mode="json")}
        speech = f"Modello {result.spec.name} generato: {stats['parts']} parti, {stats['faces']} facce, file {', '.join(result.written)}."
        return self._reply(request, started, "SUCCESS", data, speech)

    def _reply(self, request: AgentTaskRequest, started: float, status: str, data: dict, speech: str) -> AgentTaskResponse:
        return AgentTaskResponse(
            task_id=request.task_id,
            agent_id=self.agent_id,
            status=status,
            result_data=data,
            speech_output=speech,
            execution_time_ms=(time.time() - started) * 1000,
        )
