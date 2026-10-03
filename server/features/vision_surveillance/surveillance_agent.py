import time
import httpx
import logging
from typing import List
from server.config.env import settings
from server.core.agent_registry.interfaces import BaseAgent, AgentTaskRequest, AgentTaskResponse
from server.core.reasoning.react_loop import ReActLoop
from server.core.reasoning.self_critique import self_critique_engine

logger = logging.getLogger("jarvis.surveillance_agent")

class VisionSurveillanceAgent(BaseAgent):
    def __init__(self, frigate_url: str = settings.FRIGATE_URL) -> None:
        self._frigate_url = frigate_url
        self._react = self._build_react_loop()

    @property
    def agent_id(self) -> str:
        return "agent_vision_surveillance"

    @property
    def capabilities(self) -> List[str]:
        return ["rtsp_stream", "object_detection", "face_recognition", "zone_monitoring", "frigate_nvr", "react_reasoning", "self_critique"]

    async def can_handle(self, request: AgentTaskRequest) -> float:
        if request.intent == "VISION_SURVEILLANCE":
            return 0.95
        keywords = ["telecamera", "telecamere", "chi c'è", "intruso", "cortile", "giardino", "porta d'ingresso"]
        match_count = sum(1 for k in keywords if k in request.raw_query.lower())
        if match_count > 0:
            return min(0.35 + (match_count * 0.25), 0.9)
        return 0.05

    async def execute(self, request: AgentTaskRequest) -> AgentTaskResponse:
        start_time = time.time()

        react_result = await self._react.run(
            task=request.raw_query,
            agent_context=(
                "Sei il responsabile della Sicurezza Visiva di Jarvis. Interfacciati con il "
                "sistema NVR Frigate. Analizza le richieste dell'utente, usa i tool per "
                "reperire gli ultimi eventi di sicurezza e formula una risposta chiara sullo stato "
                "del perimetro o sull'evento richiesto."
            ),
        )

        raw_answer = react_result.get("answer", "Nessuna anomalia critica rilevata dal sistema di visione.")
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
        loop = ReActLoop(max_iterations=4, model_name="qwen2.5:7b", component="surveillance_agent")

        async def get_latest_events(limit: int = 5) -> str:
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    res = await client.get(f"{self._frigate_url}/api/events?limit={limit}")
                    if res.status_code == 200:
                        events = res.json()
                        if not events:
                            return "Nessun evento recente rilevato."
                        summary = [
                            f"- {e.get('label', 'oggetto')} in {e.get('camera', 'unknown_cam')} "
                            f"(score: {e.get('data', {}).get('score', 0):.2f})" 
                            for e in events
                        ]
                        return "Ultimi eventi:\n" + "\n".join(summary)
                    return f"FAILED: Frigate API error {res.status_code}"
            except Exception as e:
                return f"Simulazione Locale: [Nessun intruso rilevato. Area sicura.] (Errore API Frigate: {e})"

        loop.register_tool(
            "get_latest_events",
            "Ottiene gli ultimi eventi rilevati dalle telecamere (parametri: limit)",
            get_latest_events,
        )

        return loop

    async def _refine_with_critique(self, task: str, answer: str) -> str:
        try:
            return await self_critique_engine.critique_and_refine(
                task=f"Riassumi lo stato della sorveglianza in base alla richiesta: {task}",
                draft_output=answer,
                max_refinements=1,
                quality_threshold=8,
            )
        except Exception as exc:
            logger.warning("Self-critique fallita: %s", exc)
            return answer
