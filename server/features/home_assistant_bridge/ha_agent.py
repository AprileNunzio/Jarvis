import time
import httpx
import logging
from typing import List
from server.config.env import settings
from server.core.agent_registry.interfaces import BaseAgent, AgentTaskRequest, AgentTaskResponse
from server.core.reasoning.react_loop import ReActLoop
from server.core.reasoning.self_critique import self_critique_engine

logger = logging.getLogger("jarvis.ha_agent")

class HomeAssistantAgent(BaseAgent):
    def __init__(self, base_url: str = settings.HOME_ASSISTANT_URL, token: str = settings.HOME_ASSISTANT_TOKEN) -> None:
        self._base_url = base_url
        self._token = token
        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json"
        }
        self._react = self._build_react_loop()

    @property
    def agent_id(self) -> str:
        return "agent_home_assistant"

    @property
    def capabilities(self) -> List[str]:
        return ["lights", "climate", "covers", "switches", "scenes", "automations", "react_reasoning", "self_critique"]

    async def can_handle(self, request: AgentTaskRequest) -> float:
        if request.intent == "HOME_AUTOMATION":
            return 0.95
        keywords = ["luce", "luci", "spegni", "accendi", "termostato", "aria condizionata", "tapparelle", "cancello"]
        match_count = sum(1 for k in keywords if k in request.raw_query.lower())
        if match_count > 0:
            return min(0.3 + (match_count * 0.25), 0.9)
        return 0.05

    async def execute(self, request: AgentTaskRequest) -> AgentTaskResponse:
        start_time = time.time()
        
        react_result = await self._react.run(
            task=request.raw_query,
            agent_context=(
                "Sei il gestore della Domotica di Jarvis. Controlli Home Assistant. "
                "Il tuo compito è capire l'ambiente, decidere il dominio e l'entità corretti "
                "ed eseguire l'azione con il tool ha_call_service. "
                "Concludi specificando cosa hai fatto."
            ),
        )

        raw_answer = react_result.get("answer", "Azione non determinata correttamente.")
        refined_answer = await self._refine_with_critique(request.raw_query, raw_answer)

        elapsed = (time.time() - start_time) * 1000
        return AgentTaskResponse(
            task_id=request.task_id,
            agent_id=self.agent_id,
            status="SUCCESS" if react_result.get("success") else "PARTIAL",
            result_data={
                "react_iterations": react_result.get("iterations", 0),
                "trajectory": react_result.get("trajectory", [])
            },
            speech_output=refined_answer,
            execution_time_ms=elapsed
        )

    def _build_react_loop(self) -> ReActLoop:
        loop = ReActLoop(max_iterations=4, model_name="qwen2.5:7b")

        async def ha_call_service(domain: str, service: str, entity_id: str) -> str:
            if not self._token:
                return f"Simulazione Locale: Servizio {domain}.{service} chiamato su {entity_id} (Nessun token impostato)."
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    res = await client.post(
                        f"{self._base_url}/api/services/{domain}/{service}",
                        headers=self._headers,
                        json={"entity_id": entity_id} if entity_id != "all" else {}
                    )
                    if res.status_code in [200, 201]:
                        return f"SUCCESS: Chiamata a {domain}.{service} su {entity_id} completata."
                    return f"FAILED: Errore {res.status_code} da Home Assistant."
            except Exception as e:
                return f"FAILED: Errore di connessione a Home Assistant ({e})"

        async def ha_get_states() -> str:
            if not self._token:
                return "Mock: [light.living_room (on), light.kitchen (off), climate.bedroom (off)]"
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    res = await client.get(
                        f"{self._base_url}/api/states",
                        headers=self._headers
                    )
                    if res.status_code == 200:
                        states = res.json()
                        summary = [f"{s['entity_id']} ({s['state']})" for s in states if s['entity_id'].startswith(('light', 'climate', 'switch', 'cover'))]
                        return "Stati: " + ", ".join(summary[:30])
                    return f"FAILED: Errore {res.status_code}"
            except Exception as e:
                return f"FAILED: Errore ({e})"

        loop.register_tool(
            "ha_call_service",
            "Chiama un servizio su Home Assistant (parametri: domain, service, entity_id)",
            ha_call_service,
        )
        loop.register_tool(
            "ha_get_states",
            "Ottiene lo stato attuale delle entità principali per capire la situazione della casa",
            ha_get_states,
        )

        return loop

    async def _refine_with_critique(self, task: str, answer: str) -> str:
        try:
            return await self_critique_engine.critique_and_refine(
                task=f"Riassumi le azioni domotiche eseguite per: {task}",
                draft_output=answer,
                max_refinements=1,
                quality_threshold=8,
            )
        except Exception as exc:
            logger.warning("Self-critique fallita, uso l'originale: %s", exc)
            return answer
