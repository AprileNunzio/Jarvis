import json
import logging
from typing import Optional

from server.core.kernel.domain.dag import MAX_NODES, ExecutionDag
from server.core.kernel.domain.errors import DagError
from server.core.kernel.domain.node import NodeKind, NodeSpec
from server.core.kernel.domain.plan_codec import dag_from_plan, extract_json_array
from server.features.llm_gateway.contracts import LLMMessage, LLMRequest
from server.features.llm_gateway.gateway import llm_gateway

logger = logging.getLogger("jarvis.task_planner")

_KINDS = ", ".join(k.value for k in NodeKind)
_PLANNER_SYSTEM_PROMPT = f"""Sei il pianificatore strategico di Jarvis.
Trasforma la richiesta in un grafo aciclico di sotto-task atomici, isolati e verificabili.

Rispondi con un JSON array. Ogni elemento DEVE avere:
- "step": numero progressivo (intero, da 1)
- "description": cosa fare, concreto e verificabile
- "depends_on": lista dei numeri di step prerequisiti ([] se indipendente)
- "estimated_intent": intent più adatto tra {{intents}}
- "kind": uno tra {_KINDS}
- "risk": READ_ONLY, REVERSIBLE oppure DESTRUCTIVE (DESTRUCTIVE se modifica file system, git o transazioni)

Regole:
- Nessun ciclo: uno step può dipendere solo da step con numero più basso.
- Massimo {MAX_NODES} step, ognuno eseguibile da un singolo agente.
- Rispondi SOLO con il JSON array."""


class DagPlanner:
    def __init__(self, model_name: str = "qwen2.5:7b", max_planning_attempts: int = 2) -> None:
        self._model = model_name
        self._attempts = max_planning_attempts

    async def should_decompose(self, query: str) -> bool:
        response = await self._ask(
            query,
            "Analizza questa richiesta. È un task complesso che richiede più passi coordinati, "
            'oppure è un task singolo semplice?\nRispondi SOLO con: {"complex": true} oppure {"complex": false}',
            max_tokens=30,
        )
        try:
            raw = response.strip()
            return bool(json.loads(raw[raw.find("{") : raw.rfind("}") + 1]).get("complex", False))
        except (json.JSONDecodeError, AttributeError):
            return False

    async def plan(self, task: str) -> ExecutionDag:
        from server.core.orchestrator.intent_classifier import INTENT_CATALOG

        system = _PLANNER_SYSTEM_PROMPT.replace("{intents}", str(list(INTENT_CATALOG.keys())))
        request = task
        for attempt in range(1, self._attempts + 1):
            raw = await self._ask(request, system, max_tokens=1500)
            try:
                dag = dag_from_plan(extract_json_array(raw))
                logger.info("plan %s with %d nodes", dag.fingerprint()[:12], len(dag.nodes))
                return dag
            except DagError as exc:
                logger.warning("planning attempt %d rejected: %s", attempt, exc)
                request = f"{task}\n\nIl piano precedente era invalido ({exc}). Produci un piano corretto."
        return self.single_node(task)

    @staticmethod
    def single_node(task: str, intent: Optional[str] = None) -> ExecutionDag:
        return ExecutionDag.build([NodeSpec(node_id="n1", kind=NodeKind.REASONING, description=task, intent=intent or "GENERAL_INTELLIGENCE")])

    async def _ask(self, content: str, system: str, max_tokens: int) -> str:
        response = await llm_gateway.generate_completion(
            LLMRequest(
                model_name=self._model,
                messages=[LLMMessage(role="user", content=content)],
                system_prompt=system,
                temperature=0.1,
                max_tokens=max_tokens,
                component="kernel_planner",
            )
        )
        return response.content


task_planner = DagPlanner()
