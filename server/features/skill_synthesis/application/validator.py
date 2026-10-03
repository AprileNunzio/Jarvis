from server.core.kernel.domain.node import NodeSpec
from server.core.kernel.domain.outcome import NodeResult, Verdict
from server.features.skill_synthesis.application.ports import ToolStore
from server.features.skill_synthesis.application.runner import DynamicToolRunner


class ToolArtifactValidator:
    def __init__(self, store: ToolStore, runner: DynamicToolRunner) -> None:
        self._store = store
        self._runner = runner

    async def judge(self, node: NodeSpec, result: NodeResult) -> Verdict:
        name = result.output.get("tool")
        tool = self._store.get(name) if isinstance(name, str) else None
        if tool is None:
            return Verdict.reject("missing_artifact", "the node did not produce a registered tool")
        if not isinstance(result.output.get("data"), dict) or not result.output["data"]:
            return Verdict.reject("empty_result", "the tool produced no structured data")
        run = await self._runner.run(tool, tool.test_input)
        if not run.ok:
            denied = f" (host bloccati: {', '.join(run.denied_hosts)})" if run.denied_hosts else ""
            return Verdict.reject("tool_failure", f"{run.error}{denied}")
        return Verdict.accept()
