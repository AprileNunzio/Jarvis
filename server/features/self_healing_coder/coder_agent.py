import logging
import os
import time
from typing import List, Dict, Any
from server.core.agent_registry.interfaces import BaseAgent, AgentTaskRequest, AgentTaskResponse
from server.features.self_healing_coder.sandbox_runner import sandbox_runner
from server.features.llm_gateway.gateway import llm_gateway
from server.features.llm_gateway.contracts import LLMRequest, LLMMessage
from server.core.reasoning.react_loop import ReActLoop
from server.core.reasoning.self_critique import self_critique_engine
from server.features.deep_memory.composition import deep_memory
from server.features.self_healing_coder.workspace_files import WorkspaceError, WorkspaceFiles

logger = logging.getLogger("jarvis.coder_agent")

_structure = deep_memory.workspace("workspace")
workspace_files = WorkspaceFiles(os.path.join("data", "workspace"), lambda: _structure)


class SelfHealingCoderAgent(BaseAgent):

    def __init__(self) -> None:
        self._react = self._build_react_loop()

    @property
    def agent_id(self) -> str:
        return "agent_self_healing_coder"

    @property
    def capabilities(self) -> List[str]:
        return [
            "code_synthesis",
            "bug_fixing",
            "ast_refactoring",
            "sandbox_validation",
            "git_patching",
            "react_reasoning",
            "self_critique",
        ]

    async def can_handle(self, request: AgentTaskRequest) -> float:
        if request.intent == "AUTONOMOUS_PROGRAMMING":
            return 0.95
        keywords = ["codice", "script", "programma", "funzione", "debug", "errore", "refactor", "patch", "code", "fix"]
        match_count = sum(1 for k in keywords if k in request.raw_query.lower())
        if match_count > 0:
            return min(0.3 + (match_count * 0.2), 0.9)
        return 0.05

    async def execute(self, request: AgentTaskRequest) -> AgentTaskResponse:
        start_time = time.time()

        # Incorpora le direttive architetturali rigorose richieste dall'utente
        architect_rules = (
            "Agisci come un Software Architect e Team Lead estremamente severo e professionale. "
            "Rispetta e applica rigorosamente le seguenti direttive in ogni output:\n"
            "1. Architettura: Applica i principi della Clean Architecture (SoC, SRP).\n"
            "2. Purezza del Codice: Scrivi esclusivamente codice puro. Nessun commento inutile.\n"
            "3. Limiti Strutturali: Modularizza il codice in più file.\n"
            "4. User Interface: UI responsive nativa, Material Design 3 Expressive se richiesto.\n"
            "5. Sicurezza: Approccio Zero-Trust. Prevenzione vulnerabilità OWASP (SQLi, XSS, CSRF).\n"
            "6. Error Handling: Gestione errori globale robusta.\n"
            "7. Struttura dei File: Usa 'create_directory' per generare la struttura delle cartelle e 'write_file' per scrivere ogni singolo file sorgente (PHP, JS, CSS, ecc.) fisicamente su disco nel workspace.\n"
            "8. Completezza: Riempi ogni campo e funzione in modo iper-dettagliato usando gergo professionale. Non lasciare placeholder.\n"
        )

        react_result = await self._react.run(
            task=request.raw_query,
            agent_context=architect_rules,
        )

        raw_code = self._extract_code_from_result(react_result)
        refined_code = await self._refine_with_critique(request.raw_query, raw_code)

        success, stdout, stderr = await sandbox_runner.execute_in_sandbox(refined_code)

        if not success:
            logger.warning("Sandbox failed after critique, attempting self-heal")
            healed_code = await self._self_heal(refined_code, stderr)
            success, stdout, stderr = await sandbox_runner.execute_in_sandbox(healed_code)
            if success:
                refined_code = healed_code

        speech_text = (
            "Codice generato, validato dalla self-critique e verificato nella sandbox isolata con successo."
            if success
            else "Il codice è stato generato ma presenta anomalie durante la validazione in sandbox."
        )

        elapsed = (time.time() - start_time) * 1000
        return AgentTaskResponse(
            task_id=request.task_id,
            agent_id=self.agent_id,
            status="SUCCESS" if success else "PARTIAL",
            result_data={
                "code": refined_code,
                "sandbox_success": success,
                "stdout": stdout[:2000],
                "stderr": stderr[:2000],
                "react_iterations": react_result.get("iterations", 0),
                "trajectory_length": len(react_result.get("trajectory", [])),
            },
            speech_output=speech_text,
            execution_time_ms=elapsed,
        )

    def _build_react_loop(self) -> ReActLoop:
        loop = ReActLoop(max_iterations=6, model_name="qwen2.5-coder:7b")

        async def sandbox_test(code: str) -> str:
            clean = self._clean_raw_code(code)
            success, stdout, stderr = await sandbox_runner.execute_in_sandbox(clean)
            if success:
                return f"SUCCESS. stdout: {stdout[:500]}"
            return f"FAILED. stderr: {stderr[:500]}"

        async def generate_code(requirement: str) -> str:
            response = await llm_gateway.generate_completion(
                LLMRequest(
                    model_name="qwen2.5-coder:7b",
                    messages=[LLMMessage(role="user", content=requirement)],
                    system_prompt=(
                        "Genera codice Python 3 puro ed eseguibile. "
                        "Niente markdown, niente spiegazioni, niente ```. "
                        "Solo codice Python valido."
                    ),
                    temperature=0.1,
                )
            )
            return self._clean_raw_code(response.content)

        async def fix_code(code_and_error: str) -> str:
            response = await llm_gateway.generate_completion(
                LLMRequest(
                    model_name="qwen2.5-coder:7b",
                    messages=[
                        LLMMessage(
                            role="user",
                            content=f"Fix this Python code. Return ONLY the fixed code.\n{code_and_error}",
                        )
                    ],
                    temperature=0.05,
                )
            )
            return self._clean_raw_code(response.content)

        loop.register_tool(
            "generate_code",
            "Genera codice Python o PHP o HTML puro a partire da un requisito",
            generate_code,
        )
        loop.register_tool(
            "sandbox_test",
            "Esegue codice nella sandbox",
            sandbox_test,
        )
        loop.register_tool(
            "fix_code",
            "Corregge codice",
            fix_code,
        )
        
        async def create_directory(path: str) -> str:
            try:
                return workspace_files.make_directory(path)
            except (WorkspaceError, OSError) as exc:
                return f"ERROR: {exc}"

        async def write_file(path: str, content: str) -> str:
            try:
                return workspace_files.write(path, content)
            except (WorkspaceError, OSError) as exc:
                return f"ERROR: {exc}"

        loop.register_tool("create_directory", "Crea una cartella nel workspace (usa per strutturare progetti)", create_directory)
        loop.register_tool("write_file", "Scrive il contenuto in un file nel workspace (usa per salvare codice PHP, HTML, CSS, JS)", write_file)

        return loop

    async def _refine_with_critique(self, task: str, code: str) -> str:
        if not code or len(code.strip()) < 20:
            return code
        try:
            return await self_critique_engine.critique_and_refine(
                task=f"Genera codice Python per: {task}",
                draft_output=code,
                max_refinements=1,
                quality_threshold=7,
            )
        except Exception as exc:
            logger.warning("Self-critique failed, using original: %s", exc)
            return code

    async def _self_heal(self, broken_code: str, error: str) -> str:
        response = await llm_gateway.generate_completion(
            LLMRequest(
                model_name="qwen2.5-coder:7b",
                messages=[
                    LLMMessage(
                        role="user",
                        content=(
                            f"Fix this Python code. Return ONLY the fixed Python code.\n"
                            f"Error:\n{error[:500]}\n\nCode:\n{broken_code}"
                        ),
                    )
                ],
                temperature=0.05,
            )
        )
        return self._clean_raw_code(response.content)

    def _extract_code_from_result(self, react_result: Dict[str, Any]) -> str:
        answer = react_result.get("answer", "")
        if answer and "def " in answer or "import " in answer or "class " in answer:
            return self._clean_raw_code(answer)

        trajectory = react_result.get("trajectory", [])
        for step in reversed(trajectory):
            action_input = step.get("action_input", "")
            if isinstance(action_input, str) and ("def " in action_input or "import " in action_input):
                return self._clean_raw_code(action_input)
            raw = step.get("raw_response", "")
            if "def " in raw or "import " in raw:
                return self._clean_raw_code(raw)

        return self._clean_raw_code(answer)

    @staticmethod
    def _clean_raw_code(raw_output: str) -> str:
        lines = raw_output.strip().splitlines()
        filtered = [l for l in lines if not l.startswith("```")]
        result = "\n".join(filtered).strip()
        if result.startswith("python\n"):
            result = result[7:]
        return result
