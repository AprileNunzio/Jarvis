import asyncio
import tempfile
import os
import sys
from typing import Tuple
from server.config.env import settings
from server.shared.errors.domain_errors import SandboxSecurityException

class SandboxRunner:
    def __init__(self, timeout_seconds: int = settings.CODE_SANDBOX_TIMEOUT_SECONDS) -> None:
        self._timeout = timeout_seconds

    async def execute_in_sandbox(self, python_code: str) -> Tuple[bool, str, str]:
        self._inspect_code_safety(python_code)
        
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as temp_file:
            temp_file.write(python_code)
            temp_path = temp_file.name

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-I",
                temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout_data, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=self._timeout)
            success = (proc.returncode == 0)
            return success, stdout_data.decode("utf-8", errors="replace"), stderr_data.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            proc.kill()
            raise SandboxSecurityException("Sandbox execution timed out exceeding safety limits")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _inspect_code_safety(self, code_str: str) -> None:
        forbidden_tokens = ["os.system(", "subprocess.Popen(", "shutil.rmtree('/'", "open('/etc/shadow'"]
        for token in forbidden_tokens:
            if token in code_str:
                raise SandboxSecurityException(f"Forbidden security construct detected: {token}")

sandbox_runner = SandboxRunner()
