from typing import Tuple

from server.config.env import settings
from server.features.sandbox.application.gateway import SandboxGateway
from server.features.sandbox.domain.errors import SandboxError
from server.features.sandbox.domain.spec import ResourceLimits
from server.features.sandbox.infrastructure.broker_client import BrokerClient


class SandboxRunner:
    def __init__(self, gateway: SandboxGateway, timeout_seconds: int) -> None:
        self._gateway = gateway
        self._limits = ResourceLimits(wall_seconds=timeout_seconds)

    async def execute_in_sandbox(self, python_code: str) -> Tuple[bool, str, str]:
        try:
            report = await self._gateway.run_python(python_code, limits=self._limits)
        except SandboxError as exc:
            return False, "", f"sandbox error: {exc}"
        if report.timed_out:
            return False, report.stdout, f"{report.stderr}\nexecution exceeded {self._limits.wall_seconds}s".strip()
        if report.oom_killed:
            return False, report.stdout, f"{report.stderr}\nexecution exceeded memory limit".strip()
        return report.succeeded, report.stdout, report.stderr


def build_default_runner() -> SandboxRunner:
    client = BrokerClient(settings.SANDBOX_SOCKET_PATH, lambda: settings.JARVIS_SECRET_KEY)
    return SandboxRunner(SandboxGateway(client), settings.CODE_SANDBOX_TIMEOUT_SECONDS)


sandbox_runner = build_default_runner()
