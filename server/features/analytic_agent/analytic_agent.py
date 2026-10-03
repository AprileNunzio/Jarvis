import json
import time
from typing import Any, Dict, List

from server.config.env import settings
from server.core.agent_registry.interfaces import AgentTaskRequest, AgentTaskResponse, BaseAgent
from server.features.llm_gateway.contracts import LLMMessage, LLMRequest
from server.features.llm_gateway.gateway import llm_gateway

_SYSTEM_PROMPT = (
    "Sei l'analista di Jarvis. Risolvi esclusivamente il sotto-task indicato, usando i risultati dei passi "
    "precedenti quando servono. Rispondi in modo concreto, completo e verificabile, senza premesse. "
    "Se il tentativo precedente è fallito, correggi esattamente il problema segnalato."
)
_CONTEXT_LIMIT = 4000
_DEFAULT_MODEL = "qwen2.5:7b"


class AnalyticReasonerAgent(BaseAgent):
    @property
    def agent_id(self) -> str:
        return "analytic_reasoner"

    @property
    def capabilities(self) -> List[str]:
        return ["analysis", "planning", "summarisation", "pure_reasoning"]

    async def can_handle(self, request: AgentTaskRequest) -> float:
        in_plan = bool(request.parameters.get("plan_context"))
        return 0.9 if in_plan and request.intent == "GENERAL_INTELLIGENCE" else 0.0

    async def execute(self, request: AgentTaskRequest) -> AgentTaskResponse:
        started = time.time()
        response = await llm_gateway.generate_completion(
            LLMRequest(
                model_name=settings.JARVIS_LLM_MODEL or _DEFAULT_MODEL,
                models=[request.preferred_brain] if request.preferred_brain else [],
                component="analytic_reasoner",
                messages=[LLMMessage(role="user", content=self._prompt(request))],
                system_prompt=_SYSTEM_PROMPT,
                temperature=0.2,
                max_tokens=1200,
            )
        )
        elapsed = (time.time() - started) * 1000
        if response.is_synthetic or not response.content.strip():
            return AgentTaskResponse(
                task_id=request.task_id,
                agent_id=self.agent_id,
                status="ERROR",
                result_data={"reason": "no language model answered"},
                speech_output="",
                execution_time_ms=elapsed,
            )
        return AgentTaskResponse(
            task_id=request.task_id,
            agent_id=self.agent_id,
            status="SUCCESS",
            result_data={"model": response.model_used},
            speech_output=response.content.strip(),
            execution_time_ms=elapsed,
        )

    @staticmethod
    def _prompt(request: AgentTaskRequest) -> str:
        previous: Dict[str, Any] = request.parameters.get("previous_results") or {}
        context = json.dumps(previous, ensure_ascii=False, default=str)[:_CONTEXT_LIMIT]
        return (
            f"Obiettivo generale: {request.parameters.get('plan_context', '')}\n\n"
            f"Risultati dei passi precedenti: {context}\n\n"
            f"Sotto-task da svolgere:\n{request.raw_query}"
        )
