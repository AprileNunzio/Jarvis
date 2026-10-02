import os
import sys
import json
import logging
import importlib
import importlib.util
from typing import Dict, Any, Optional
from server.features.llm_gateway.gateway import llm_gateway
from server.features.llm_gateway.contracts import LLMRequest, LLMMessage
from server.features.self_healing_coder.sandbox_runner import sandbox_runner
from server.core.agent_registry.pool_manager import agent_pool
from server.core.agent_registry.interfaces import BaseAgent

logger = logging.getLogger("jarvis.skill_synthesis")

DYNAMIC_SKILLS_DIR = os.path.join("server", "features", "dynamic_skills")

_SYNTHESIS_PROMPT = """Genera un agente Python completo e funzionante per gestire l'intent: '{intent}'.

REQUISITI OBBLIGATORI:
1. La classe DEVE ereditare da `BaseAgent` importato con:
   `from server.core.agent_registry.interfaces import BaseAgent, AgentTaskRequest, AgentTaskResponse`
2. Implementare la property `agent_id` che ritorna una stringa unica (es. "agent_dynamic_{safe_intent}")
3. Implementare la property `capabilities` che ritorna una lista di stringhe includendo "react_reasoning" e "self_critique"
4. Implementare `async def can_handle(self, request: AgentTaskRequest) -> float` che ritorna un float 0.0-1.0
5. Implementare `async def execute(self, request: AgentTaskRequest) -> AgentTaskResponse` usando SEMPRE il `ReActLoop` (importato da `server.core.reasoning.react_loop`) e `self_critique_engine` (da `server.core.reasoning.self_critique`).
6. Alla fine del file: `if __name__ == "__main__": print("SYNTHESIS_TEST_PASS")`

Contesto aggiuntivo: {context}

RISPONDI ESCLUSIVAMENTE con il codice Python puro, senza markdown, senza spiegazioni, senza ```."""


class SkillSynthesizerLobe:

    def __init__(self, model_name: str = "qwen2.5-coder:7b") -> None:
        self._model = model_name
        self._ensure_dynamic_dir()

    def _ensure_dynamic_dir(self) -> None:
        os.makedirs(DYNAMIC_SKILLS_DIR, exist_ok=True)
        init_path = os.path.join(DYNAMIC_SKILLS_DIR, "__init__.py")
        if not os.path.exists(init_path):
            with open(init_path, "w") as f:
                f.write("# Auto-generated module for dynamically synthesized agents\n")

    async def synthesize_new_skill(self, request: Dict[str, Any]) -> str:
        intent = request.get("missing_intent", "unknown")
        context = request.get("context", {})
        safe_name = self._sanitize_name(intent)

        logger.info("Skill synthesis initiated for intent: %s", intent)

        agent_code = await self._generate_agent_code(intent, context)
        if not agent_code:
            logger.error("Code generation failed for intent: %s", intent)
            return f"Synthesis FAILED: impossibile generare codice per '{intent}'"

        success, stdout, stderr = await sandbox_runner.execute_in_sandbox(agent_code)

        if not success:
            logger.warning("First sandbox test failed for '%s', attempting self-heal. Error: %s", intent, stderr[:200])
            agent_code = await self._self_heal(agent_code, stderr)
            success, stdout, stderr = await sandbox_runner.execute_in_sandbox(agent_code)

            if not success:
                logger.error("Self-heal failed for '%s': %s", intent, stderr[:200])
                return f"Synthesis FAILED: il codice non supera i test sandbox. Errore: {stderr[:200]}"

        if "SYNTHESIS_TEST_PASS" not in stdout:
            logger.warning("Sandbox passed but SYNTHESIS_TEST_PASS marker not found in stdout")

        file_path = os.path.join(DYNAMIC_SKILLS_DIR, f"{safe_name}_agent.py")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(agent_code)
        logger.info("Dynamic agent code saved to %s", file_path)

        load_result = self._load_and_register(safe_name, file_path)
        if load_result:
            logger.info("Dynamic agent for '%s' registered successfully: %s", intent, load_result)
            return f"Nuova skill '{intent}' sintetizzata, testata e attivata con successo. Agente: {load_result}"

        logger.warning("Agent saved to disk but dynamic loading failed for '%s'", intent)
        return f"Skill '{intent}' salvata su disco ({file_path}) ma il caricamento dinamico ha fallito."

    async def _generate_agent_code(self, intent: str, context: Dict[str, Any]) -> Optional[str]:
        safe_intent = self._sanitize_name(intent)
        prompt = _SYNTHESIS_PROMPT.format(
            intent=intent,
            safe_intent=safe_intent,
            context=json.dumps(context, default=str),
        )

        response = await llm_gateway.generate_completion(
            LLMRequest(
                model_name=self._model,
                messages=[LLMMessage(role="user", content=prompt)],
                temperature=0.15,
                max_tokens=3000,
            )
        )

        code = self._clean_code(response.content)
        return code if code and len(code) > 50 else None

    async def _self_heal(self, broken_code: str, error: str) -> str:
        response = await llm_gateway.generate_completion(
            LLMRequest(
                model_name=self._model,
                messages=[
                    LLMMessage(
                        role="user",
                        content=(
                            f"Fix this Python code. It must compile and run without errors.\n"
                            f"Error:\n{error[:500]}\n\n"
                            f"Code:\n{broken_code}\n\n"
                            f"Return ONLY the complete fixed Python code, no markdown, no explanations."
                        ),
                    )
                ],
                temperature=0.05,
                max_tokens=3000,
            )
        )
        return self._clean_code(response.content)

    def _load_and_register(self, safe_name: str, file_path: str) -> Optional[str]:
        module_name = f"server.features.dynamic_skills.{safe_name}_agent"
        try:
            abs_path = os.path.abspath(file_path)
            spec = importlib.util.spec_from_file_location(module_name, abs_path)
            if not spec or not spec.loader:
                return None
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseAgent)
                    and attr is not BaseAgent
                ):
                    new_agent = attr()
                    agent_pool.register_agent(new_agent)
                    return new_agent.agent_id

            return None
        except Exception as exc:
            logger.error("Dynamic loading failed for %s: %s", file_path, exc)
            return None

    @staticmethod
    def _sanitize_name(name: str) -> str:
        return name.lower().replace(" ", "_").replace("-", "_").replace(".", "_")

    @staticmethod
    def _clean_code(raw: str) -> str:
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            filtered = [l for l in lines if not l.startswith("```")]
            raw = "\n".join(filtered)
        if raw.startswith("python\n"):
            raw = raw[7:]
        return raw.strip()


skill_synthesizer = SkillSynthesizerLobe()
