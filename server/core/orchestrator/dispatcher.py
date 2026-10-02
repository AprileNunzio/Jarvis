import time
import uuid
import logging
from typing import Dict, Any, Optional
from server.core.agent_registry.interfaces import AgentTaskRequest, AgentTaskResponse
from server.core.agent_registry.pool_manager import agent_pool
from server.core.context_graph.graph_client import graph_client
from server.core.context_graph.node_schema import NodeType, RelationType
from server.core.orchestrator.intent_classifier import intent_classifier
from server.core.planner.task_decomposer import task_planner
from server.features.skill_synthesis.synthesizer_lobe import skill_synthesizer
from server.shared.utils.text_sanitizer import TextSanitizer
from server.core.reasoning.conversation import conversation_engine


logger = logging.getLogger("jarvis.dispatcher")


class OrchestratorDispatcher:

    def __init__(self) -> None:
        self._sanitizer = TextSanitizer()

    async def dispatch_user_command(
        self,
        raw_query: str,
        speaker_id: str,
        device_id: str,
        biometric_score: float,
        context_override: Optional[Dict[str, Any]] = None,
    ) -> AgentTaskResponse:
        sanitized_query = self._sanitizer.sanitize_plain_text(raw_query)


        task_id = f"tsk_{uuid.uuid4().hex[:12]}"

        graph_client.upsert_node(
            node_id=speaker_id,
            node_type=NodeType.USER,
            label=f"User {speaker_id}",
            properties={"last_seen": time.time(), "biometric_confidence": biometric_score},
        )

        graph_client.upsert_node(
            node_id=task_id,
            node_type=NodeType.CONCEPT,
            label=f"Task: {sanitized_query[:40]}",
            properties={"raw_query": sanitized_query, "status": "CLASSIFYING"},
        )

        graph_client.link_nodes(
            source_id=speaker_id,
            target_id=task_id,
            relation_type=RelationType.TRIGGERED_BY,
            weight=biometric_score,
        )

        if intent_classifier._keyword_fallback(sanitized_query) == "GENERAL_INTELLIGENCE" and len(sanitized_query) < 240:
            extracted_intent, confidence = "GENERAL_INTELLIGENCE", 0.7
        else:
            extracted_intent, confidence = await intent_classifier.classify(sanitized_query)
        logger.info("Intent: %s (confidence: %.2f) for query: %s", extracted_intent, confidence, sanitized_query[:60])

        graph_client.upsert_node(
            node_id=task_id,
            node_type=NodeType.CONCEPT,
            label=f"Task: {sanitized_query[:40]}",
            properties={"intent": extracted_intent, "intent_confidence": confidence, "status": "PLANNING"},
        )

        if extracted_intent == "GENERAL_INTELLIGENCE":
            started = time.time()
            answer = await conversation_engine.reply(
                sanitized_query, device_id, people_context=(context_override or {}).get("people_present", ""),
                knowledge=(context_override or {}).get("knowledge", ""),
                models=(context_override or {}).get("models") or None,
                max_tokens=(context_override or {}).get("max_tokens") or 400,
                reply_language=str((context_override or {}).get("reply_language") or ""),
                speaker=str((context_override or {}).get("speaker") or ""),
                dialogue=str((context_override or {}).get("dialogue") or ""),
                long_term=str((context_override or {}).get("long_term") or ""),
                laws=str((context_override or {}).get("laws") or ""),
                pinned=str((context_override or {}).get("pinned") or ""))
            graph_client.upsert_node(
                node_id=task_id,
                node_type=NodeType.CONCEPT,
                label=f"Task: {sanitized_query[:40]}",
                properties={"status": "COMPLETED", "speech_output": answer[:200]},
            )
            return AgentTaskResponse(
                task_id=task_id,
                agent_id="jarvis_conversation",
                status="SUCCESS",
                result_data={"intent": extracted_intent, "confidence": confidence,
                             "model": conversation_engine.last_model},
                speech_output=answer,
                execution_time_ms=(time.time() - started) * 1000,
            )

        is_complex = await task_planner.should_decompose(sanitized_query)

        if is_complex:
            logger.info("Complex task detected, decomposing into sub-tasks")
            plan = await task_planner.decompose(sanitized_query)

            graph_client.upsert_node(
                node_id=task_id,
                node_type=NodeType.CONCEPT,
                label=f"Task: {sanitized_query[:40]}",
                properties={"status": "EXECUTING_PLAN", "plan_steps": len(plan)},
            )

            plan_result = await task_planner.execute_plan(
                plan=plan,
                original_query=sanitized_query,
                user_id=speaker_id,
                device_id=device_id,
            )

            execution_summary = "; ".join(
                f"Step {r['step']}: {r.get('speech', r.get('status', 'DONE'))}"
                for r in plan_result.get("execution", [])
            )

            elapsed = (time.time() - float(graph_client.get_node(task_id).properties.get("last_seen", time.time()))) * 1000

            speech_output = (
                f"Piano eseguito: {plan_result['completed_steps']}/{plan_result['total_steps']} step completati. "
                + execution_summary[:300]
            )

            graph_client.upsert_node(
                node_id=task_id,
                node_type=NodeType.CONCEPT,
                label=f"Task: {sanitized_query[:40]}",
                properties={
                    "status": "COMPLETED" if plan_result["fully_completed"] else "PARTIAL",
                    "plan_result": plan_result,
                },
            )

            return AgentTaskResponse(
                task_id=task_id,
                agent_id="orchestrator_planner",
                status="SUCCESS" if plan_result["fully_completed"] else "PARTIAL",
                result_data=plan_result,
                speech_output=speech_output,
                execution_time_ms=elapsed,
            )

        task_request = AgentTaskRequest(
            task_id=task_id,
            user_id=speaker_id,
            intent=extracted_intent,
            raw_query=sanitized_query,
            confidence=confidence,
            parameters={
                "device_id": device_id,
                "biometric_score": biometric_score,
                **(context_override or {}),
            },
        )

        try:
            assigned_agent = await agent_pool.select_best_agent(task_request)
        except Exception:
            logger.warning("No agent for intent '%s', triggering skill synthesis", extracted_intent)
            synthesis_result = await skill_synthesizer.synthesize_new_skill({
                "missing_intent": extracted_intent,
                "context": {"query": sanitized_query, "device_id": device_id},
            })

            try:
                assigned_agent = await agent_pool.select_best_agent(task_request)
            except Exception:
                elapsed = (time.time()) * 1000
                return AgentTaskResponse(
                    task_id=task_id,
                    agent_id="skill_synthesizer",
                    status="SYNTHESIS_ATTEMPTED",
                    result_data={"synthesis_result": synthesis_result},
                    speech_output=synthesis_result,
                    execution_time_ms=0,
                )

        graph_client.upsert_node(
            node_id=assigned_agent.agent_id,
            node_type=NodeType.AGENT,
            label=assigned_agent.agent_id.replace("_", " ").title(),
            properties={"capabilities": assigned_agent.capabilities},
        )

        graph_client.link_nodes(
            source_id=task_id,
            target_id=assigned_agent.agent_id,
            relation_type=RelationType.DEPENDS_ON,
        )

        graph_client.upsert_node(
            node_id=task_id,
            node_type=NodeType.CONCEPT,
            label=f"Task: {sanitized_query[:40]}",
            properties={"status": "EXECUTING", "assigned_agent": assigned_agent.agent_id},
        )

        response = await assigned_agent.execute(task_request)

        graph_client.upsert_node(
            node_id=task_id,
            node_type=NodeType.CONCEPT,
            label=f"Task: {sanitized_query[:40]}",
            properties={
                "status": response.status,
                "execution_time_ms": response.execution_time_ms,
                "speech_output": response.speech_output[:200],
            },
        )

        return response


orchestrator_dispatcher = OrchestratorDispatcher()
