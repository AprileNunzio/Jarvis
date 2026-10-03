from typing import Protocol

from server.features.sandbox.domain.report import ExecutionReport
from server.features.sandbox.domain.spec import ExecutionSpec


class SandboxPort(Protocol):
    async def execute(self, spec: ExecutionSpec) -> ExecutionReport: ...
