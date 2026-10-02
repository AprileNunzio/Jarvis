import secrets
import time
import logging
from typing import List
from server.core.agent_registry.interfaces import BaseAgent, AgentTaskRequest, AgentTaskResponse
from server.features.sysops_automation.ssh_executor import shell_executor, CommandExecutionRequest
from server.features.sysops_automation.smb_manager import smb_manager, SmbShareRequest
from server.features.sysops_automation.mysql_provisioner import mysql_provisioner, MySQLProvisionRequest
from server.features.sysops_automation.app_scaffolder import app_scaffolder, AppScaffoldRequest
from server.core.reasoning.react_loop import ReActLoop
from server.core.reasoning.self_critique import self_critique_engine

logger = logging.getLogger("jarvis.sysops_agent")

class SysOpsAutomationAgent(BaseAgent):
    def __init__(self) -> None:
        self._react = self._build_react_loop()

    @property
    def agent_id(self) -> str:
        return "agent_sysops_automation"

    @property
    def capabilities(self) -> List[str]:
        return [
            "debian_bash",
            "powershell_cmd",
            "ssh_remote",
            "smb_share_create",
            "mysql_db_provision",
            "app_scaffold",
            "react_reasoning",
            "self_critique"
        ]

    async def can_handle(self, request: AgentTaskRequest) -> float:
        if request.intent == "SYSOPS_AUTOMATION":
            return 0.95
        keywords = [
            "ssh", "powershell", "pwsh", "debian", "bash", "comando", "terminale",
            "smb", "samba", "cartella condivisa", "condividi",
            "mysql", "mariadb", "database", "crea app", "crea applicazione", "scaffold"
        ]
        lowered = request.raw_query.lower()
        match_count = sum(1 for k in keywords if k in lowered)
        if match_count > 0:
            return min(0.4 + (match_count * 0.2), 0.98)
        return 0.05

    async def execute(self, request: AgentTaskRequest) -> AgentTaskResponse:
        start_time = time.time()
        
        react_result = await self._react.run(
            task=request.raw_query,
            agent_context=(
                "Sei il SysOps di Jarvis. Il tuo compito è automatizzare server, "
                "eseguire comandi bash/powershell, configurare DB, SMB o fare scaffold. "
                "Scomponi le richieste in comandi atomici, esegui i tool necessari, "
                "verifica se sono andati a buon fine, se falliscono prova a correggere, "
                "infine rispondi comunicando esplicitamente cosa hai fatto."
            ),
        )

        raw_answer = react_result.get("answer", "Azione di amministrazione di sistema completata con esito incerto.")
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
        loop = ReActLoop(max_iterations=6, model_name="qwen2.5-coder:7b")

        async def run_shell_command(shell_type: str, command: str) -> str:
            res = await shell_executor.execute_command(
                CommandExecutionRequest(shell_type=shell_type, command=command)
            )
            return f"EXIT_CODE: {res.exit_code}\nSTDOUT: {res.stdout[:1000]}\nSTDERR: {res.stderr[:1000]}"

        async def create_smb_share(share_name: str, directory_path: str) -> str:
            success = await smb_manager.create_or_update_share(
                SmbShareRequest(share_name=share_name, directory_path=directory_path)
            )
            return "SUCCESS" if success else "FAILED"

        async def provision_mysql(database_name: str, username: str) -> str:
            password = secrets.token_urlsafe(18)
            success = await mysql_provisioner.provision_database(
                MySQLProvisionRequest(database_name=database_name, username=username, password=password)
            )
            return f"SUCCESS password={password}" if success else "FAILED"

        async def scaffold_app(app_name: str, target_directory: str) -> str:
            success = await app_scaffolder.scaffold_application(
                AppScaffoldRequest(app_name=app_name, template_type="fastapi", target_directory=target_directory)
            )
            return "SUCCESS" if success else "FAILED"

        loop.register_tool(
            "run_shell_command",
            "Esegue un comando shell (parametri: shell_type ['bash' o 'powershell'], command). Usa questo per operazioni OS generiche.",
            run_shell_command,
        )
        loop.register_tool(
            "create_smb_share",
            "Crea una cartella condivisa Samba (parametri: share_name, directory_path)",
            create_smb_share,
        )
        loop.register_tool(
            "provision_mysql",
            "Crea un database MySQL e l'utente relativo (parametri: database_name, username)",
            provision_mysql,
        )
        loop.register_tool(
            "scaffold_app",
            "Crea lo scheletro di una nuova app FastAPI (parametri: app_name, target_directory)",
            scaffold_app,
        )

        return loop

    async def _refine_with_critique(self, task: str, answer: str) -> str:
        try:
            return await self_critique_engine.critique_and_refine(
                task=f"Sintetizza le operazioni sistemistiche eseguite per: {task}",
                draft_output=answer,
                max_refinements=1,
                quality_threshold=8,
            )
        except Exception as exc:
            logger.warning("Self-critique fallita: %s", exc)
            return answer
