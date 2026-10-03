import ast

from server.core.kernel.domain.node import NodeSpec
from server.core.kernel.domain.outcome import NodeResult, Verdict
from server.features.sandbox.application.gateway import SandboxGateway
from server.features.sandbox.domain.errors import SandboxError
from server.features.sandbox.domain.spec import ResourceLimits

_OUTPUT_EXCERPT = 1200


class CodeArtifactValidator:
    def __init__(self, gateway: SandboxGateway, limits: ResourceLimits = ResourceLimits(wall_seconds=30)) -> None:
        self._gateway = gateway
        self._limits = limits

    async def judge(self, node: NodeSpec, result: NodeResult) -> Verdict:
        code = result.output.get("code")
        if not isinstance(code, str) or not code.strip():
            return Verdict.reject("missing_artifact", "the node produced no code")
        try:
            ast.parse(code)
        except SyntaxError as exc:
            return Verdict.reject("syntax_error", f"{exc.msg} at line {exc.lineno}", line=exc.lineno, offset=exc.offset)
        try:
            report = await self._gateway.run_python(code, limits=self._limits)
        except SandboxError as exc:
            return Verdict.reject("sandbox_unavailable", str(exc))
        if report.timed_out:
            return Verdict.reject("timeout", f"execution exceeded {self._limits.wall_seconds}s")
        if report.oom_killed:
            return Verdict.reject("memory", f"execution exceeded {self._limits.memory_mb} MB")
        if not report.succeeded:
            return Verdict.reject("runtime_error", report.stderr[-_OUTPUT_EXCERPT:], exit_code=report.exit_code)
        return Verdict.accept()
