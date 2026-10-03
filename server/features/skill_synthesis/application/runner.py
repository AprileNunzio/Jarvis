import json
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

from server.features.sandbox.application.gateway import SandboxGateway
from server.features.sandbox.domain.errors import SandboxError
from server.features.sandbox.domain.spec import ResourceLimits
from server.features.skill_synthesis.domain.tool import DynamicTool

TOOL_LIMITS = ResourceLimits(memory_mb=256, cpus=1.0, wall_seconds=60)
INPUT_FILE = "input.json"
_EXCERPT = 1500


@dataclass(frozen=True)
class ToolRun:
    ok: bool
    data: Optional[Dict[str, Any]]
    error: str
    denied_hosts: Tuple[str, ...] = ()
    stdout: str = ""


def parse_result(stdout: str) -> Optional[Dict[str, Any]]:
    lines = [line for line in stdout.strip().splitlines() if line.strip()]
    if not lines:
        return None
    try:
        value = json.loads(lines[-1])
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


class DynamicToolRunner:
    def __init__(self, gateway: SandboxGateway, limits: ResourceLimits = TOOL_LIMITS) -> None:
        self._gateway = gateway
        self._limits = limits

    async def run(self, tool: DynamicTool, payload: Mapping[str, Any]) -> ToolRun:
        inputs = {INPUT_FILE: json.dumps(payload, default=str).encode("utf-8")}
        runner = self._gateway.run_python if tool.language.value == "python" else self._gateway.run_bash
        try:
            report = await runner(tool.source, limits=self._limits, inputs=inputs, egress_hosts=tool.egress_hosts)
        except SandboxError as exc:
            return ToolRun(False, None, f"sandbox error: {exc}")
        denied = report.egress_denied
        if report.timed_out:
            return ToolRun(False, None, f"the script exceeded {self._limits.wall_seconds}s", denied, report.stdout)
        if report.oom_killed:
            return ToolRun(False, None, "the script exceeded the memory limit", denied, report.stdout)
        if not report.succeeded:
            return ToolRun(False, None, report.stderr[-_EXCERPT:] or f"exit code {report.exit_code}", denied, report.stdout)
        data = parse_result(report.stdout)
        if data is None:
            return ToolRun(False, None, "the last line printed on stdout must be a JSON object", denied, report.stdout)
        return ToolRun(True, data, "", denied, report.stdout)
