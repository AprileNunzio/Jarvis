import json
import logging
from typing import List, Dict, Any
from server.features.llm_gateway.gateway import llm_gateway
from server.features.llm_gateway.contracts import LLMRequest, LLMMessage
from server.core.agent_registry.pool_manager import agent_pool
from server.core.agent_registry.interfaces import AgentTaskRequest

logger = logging.getLogger("jarvis.task_planner")

_PLANNER_SYSTEM_PROMPT = """Sei il pianificatore strategico di Jarvis.
Decomponi la richiesta complessa dell'utente in sotto-task atomici, ordinati logicamente.

Rispondi con un JSON array. Ogni elemento DEVE avere:
- "step": numero progressivo (intero, partendo da 1)
- "description": descrizione chiara e concisa del sotto-task
- "depends_on": lista di numeri di step prerequisiti (array vuoto se indipendente)
- "estimated_intent": intent più adatto tra {intents}

Regole:
- Ogni step deve essere abbastanza specifico da essere eseguibile da un singolo agente.
- Ordina i passi in modo logico rispettando le dipendenze.
- Non superare 8 step totali.
- Rispondi SOLO con il JSON array, nessun altro testo."""


class AutonomousTaskPlanner:

    def __init__(self, model_name: str = "qwen2.5:7b") -> None:
        self._model = model_name

    async def should_decompose(self, query: str) -> bool:
        response = await llm_gateway.generate_completion(
            LLMRequest(
                model_name=self._model,
                messages=[LLMMessage(role="user", content=query)],
                system_prompt=(
                    "Analizza questa richiesta. È un task complesso che richiede più passi "
                    "coordinati, oppure è un task singolo semplice?\n"
                    'Rispondi SOLO con: {"complex": true} oppure {"complex": false}'
                ),
                temperature=0.05,
                max_tokens=30,
            )
        )
        try:
            raw = response.content.strip()
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1:
                return json.loads(raw[start : end + 1]).get("complex", False)
        except (json.JSONDecodeError, KeyError):
            pass
        return False

    async def decompose(self, complex_task: str) -> List[Dict[str, Any]]:
        from server.core.orchestrator.intent_classifier import INTENT_CATALOG

        system = _PLANNER_SYSTEM_PROMPT.format(intents=list(INTENT_CATALOG.keys()))

        response = await llm_gateway.generate_completion(
            LLMRequest(
                model_name=self._model,
                messages=[LLMMessage(role="user", content=complex_task)],
                system_prompt=system,
                temperature=0.1,
                max_tokens=1500,
            )
        )

        try:
            raw = response.content.strip()
            start = raw.find("[")
            end = raw.rfind("]")
            if start != -1 and end != -1:
                plan = json.loads(raw[start : end + 1])
                if isinstance(plan, list) and len(plan) > 0:
                    logger.info("Task decomposed into %d steps", len(plan))
                    return plan
        except json.JSONDecodeError:
            pass

        logger.warning("Decomposition failed, returning single-step plan")
        return [{"step": 1, "description": complex_task, "depends_on": [], "estimated_intent": "GENERAL_INTELLIGENCE"}]

    async def execute_plan(
        self,
        plan: List[Dict[str, Any]],
        original_query: str,
        user_id: str,
        device_id: str,
        task_id: str = None
    ) -> Dict[str, Any]:
        completed: Dict[int, Dict[str, Any]] = {}
        results: List[Dict[str, Any]] = []

        sorted_plan = sorted(plan, key=lambda s: s.get("step", 0))
        total_steps = len(sorted_plan)
        
        from server.core.orchestrator.interrupt_manager import project_manager, ProjectState
        import asyncio

        for i, step in enumerate(sorted_plan):
            step_num = step.get("step", 0)
            deps = step.get("depends_on", [])

            unmet = [d for d in deps if d not in completed]
            if unmet:
                results.append({
                    "step": step_num,
                    "status": "BLOCKED",
                    "reason": f"Unmet dependencies: {unmet}",
                })
                continue
                
            # Verifica pause se è un long running task
            if task_id and task_id in project_manager.active_tasks:
                pause_event = project_manager.active_tasks[task_id]["pause_event"]
                if not pause_event.is_set():
                    logger.info("Plan execution PAUSED for task %s", task_id)
                    await pause_event.wait()
                    logger.info("Plan execution RESUMED for task %s", task_id)
                    
            # Aggiorna il progresso del manager
            if task_id and task_id in project_manager.active_tasks:
                state_file = project_manager.active_tasks[task_id]["state_file"]
                progress = int((i / max(total_steps, 1)) * 100)
                project_manager._save_state(state_file, {"status": ProjectState.RUNNING.value, "progress": progress, "name": original_query[:40]})

            sub_request = AgentTaskRequest(
                task_id=f"plan_{step_num}",
                user_id=user_id,
                intent=step.get("estimated_intent", "GENERAL_INTELLIGENCE"),
                raw_query=step["description"],
                parameters={
                    "device_id": device_id,
                    "plan_context": original_query,
                    "previous_results": {str(k): v for k, v in completed.items()},
                },
            )

            try:
                agent = await agent_pool.select_best_agent(sub_request)
                response = await agent.execute(sub_request)
                completed[step_num] = response.result_data
                results.append({
                    "step": step_num,
                    "status": response.status,
                    "agent": response.agent_id,
                    "speech": response.speech_output,
                })
                logger.info("Plan step %d completed by %s: %s", step_num, response.agent_id, response.status)
            except Exception as exc:
                results.append({
                    "step": step_num,
                    "status": "ERROR",
                    "error": str(exc),
                })
                logger.error("Plan step %d failed: %s", step_num, exc)

        if task_id and task_id in project_manager.active_tasks:
            state_file = project_manager.active_tasks[task_id]["state_file"]
            project_manager._save_state(state_file, {"status": ProjectState.COMPLETED.value, "progress": 100, "name": original_query[:40]})

        fully_completed = len(completed) == total_steps
        return {
            "plan": plan,
            "execution": results,
            "fully_completed": fully_completed,
            "completed_steps": len(completed),
            "total_steps": len(sorted_plan),
        }


task_planner = AutonomousTaskPlanner()
