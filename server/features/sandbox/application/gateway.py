from typing import Mapping, Optional

from server.features.sandbox.application.ports import SandboxPort
from server.features.sandbox.domain.errors import SandboxRejectedError
from server.features.sandbox.domain.report import ExecutionReport
from server.features.sandbox.domain.spec import ExecutionSpec, Language, ResourceLimits
from server.features.sandbox.domain.strength import Strength


class SandboxGateway:
    def __init__(self, port: SandboxPort) -> None:
        self._port = port

    async def run(self, spec: ExecutionSpec) -> ExecutionReport:
        spec.validate()
        report = await self._port.execute(spec)
        if report.strength < spec.min_strength:
            raise SandboxRejectedError(f"backend strength {report.strength} below required {int(spec.min_strength)}")
        return report

    async def run_python(self, source: str, **options) -> ExecutionReport:
        return await self._run_source(Language.PYTHON, source, **options)

    async def run_bash(self, source: str, **options) -> ExecutionReport:
        return await self._run_source(Language.BASH, source, **options)

    async def _run_source(
        self,
        language: Language,
        source: str,
        *,
        limits: Optional[ResourceLimits] = None,
        inputs: Optional[Mapping[str, bytes]] = None,
        min_strength: Strength = Strength.CONTAINER,
    ) -> ExecutionReport:
        spec = ExecutionSpec(
            language=language,
            source=source,
            limits=limits or ResourceLimits(),
            inputs=dict(inputs or {}),
            min_strength=min_strength,
        )
        return await self.run(spec)
