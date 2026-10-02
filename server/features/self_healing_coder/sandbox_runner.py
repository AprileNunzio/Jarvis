import asyncio
from typing import Tuple
from server.config.env import settings
from server.shared.errors.domain_errors import SandboxSecurityException

class SandboxRunner:
    def __init__(self, timeout_seconds: int = settings.CODE_SANDBOX_TIMEOUT_SECONDS) -> None:
        self._timeout = timeout_seconds

    async def execute_in_sandbox(self, python_code: str) -> Tuple[bool, str, str]:
        self._inspect_code_safety(python_code)
        
        from server.core.orchestrator.sandbox import EphemeralSandbox
        sandbox = EphemeralSandbox()
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, sandbox.run_code, python_code, self._timeout)
        
        if result.get("error"):
            return False, result.get("stdout") or "", result.get("error")
        return True, result.get("stdout") or "", ""

    def _inspect_code_safety(self, code_str: str) -> None:
        forbidden_tokens = ["os.system(", "subprocess.Popen(", "shutil.rmtree('/'", "open('/etc/shadow'"]
        for token in forbidden_tokens:
            if token in code_str:
                raise SandboxSecurityException(f"Forbidden security construct detected: {token}")

sandbox_runner = SandboxRunner()
