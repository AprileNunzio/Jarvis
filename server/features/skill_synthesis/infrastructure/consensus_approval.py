from typing import Tuple

from server.core.kernel.application.ports import ConsensusPort
from server.core.kernel.domain.dag import ExecutionDag
from server.core.kernel.domain.node import NodeKind, NodeSpec, RiskLevel
from server.features.skill_synthesis.domain.tool import DynamicTool

_SOURCE_EXCERPT = 1500


class ConsensusApproval:
    def __init__(self, panel: ConsensusPort) -> None:
        self._panel = panel

    async def approve(self, tool: DynamicTool) -> Tuple[bool, str]:
        description = (
            f"Creare ed eseguire uno script {tool.language.value} che contatta gli host {', '.join(tool.egress_hosts)}. "
            f"Scopo dichiarato: {tool.description}. Codice dello script:\n{tool.source[:_SOURCE_EXCERPT]}"
        )
        dag = ExecutionDag.build([NodeSpec("tool", NodeKind.TOOL_SYNTHESIS, description, risk=RiskLevel.DESTRUCTIVE)])
        verdict = await self._panel.vote(dag)
        return verdict.approved, "; ".join(verdict.objections)[:300]
