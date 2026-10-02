import asyncio
import time
from server.features.sysops_automation.sysops_contracts import (
    CommandExecutionRequest,
    CommandExecutionResult
)
from server.shared.errors.domain_errors import SandboxSecurityException

class ShellExecutor:
    FORBIDDEN_COMMANDS = {
        "rm -rf /",
        ":(){ :|:& };:",
        "mkfs",
        "dd if=/dev/zero of=/dev/sd"
    }

    async def execute_command(self, req: CommandExecutionRequest) -> CommandExecutionResult:
        self._validate_safety(req.command)
        start_time = time.time()

        if req.target_host:
            return await self._execute_remote_ssh(req, start_time)

        if req.shell_type.lower() in ("powershell", "pwsh"):
            cmd = ["pwsh", "-NoProfile", "-NonInteractive", "-Command", req.command]
        else:
            cmd = ["bash", "-c", req.command]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=float(req.timeout_seconds)
            )
            elapsed = (time.time() - start_time) * 1000
            return CommandExecutionResult(
                success=(proc.returncode == 0),
                exit_code=proc.returncode or 0,
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
                duration_ms=elapsed
            )
        except asyncio.TimeoutError:
            proc.kill()
            elapsed = (time.time() - start_time) * 1000
            return CommandExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="Command execution timed out.",
                duration_ms=elapsed
            )

    async def _execute_remote_ssh(self, req: CommandExecutionRequest, start_time: float) -> CommandExecutionResult:
        user_host = f"{req.ssh_user}@{req.target_host}" if req.ssh_user else req.target_host
        cmd = [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=accept-new",
            "-p", str(req.ssh_port),
            user_host,
            req.command
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=float(req.timeout_seconds)
            )
            elapsed = (time.time() - start_time) * 1000
            return CommandExecutionResult(
                success=(proc.returncode == 0),
                exit_code=proc.returncode or 0,
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
                duration_ms=elapsed
            )
        except asyncio.TimeoutError:
            proc.kill()
            elapsed = (time.time() - start_time) * 1000
            return CommandExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="SSH command execution timed out.",
                duration_ms=elapsed
            )

    def _validate_safety(self, cmd_str: str) -> None:
        normalized = cmd_str.strip()
        for forbidden in self.FORBIDDEN_COMMANDS:
            if forbidden in normalized:
                raise SandboxSecurityException(f"Execution blocked for high-risk pattern: {forbidden}")

shell_executor = ShellExecutor()
