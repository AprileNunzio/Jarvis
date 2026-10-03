from typing import Optional

from server.core.agent_registry.pool_manager import AgentPoolManager
from server.core.kernel.application.ports import Checkpoint, ConsensusPort, RunObserver
from server.core.kernel.application.scheduler import DagScheduler
from server.core.kernel.application.validators import DEFAULT_VALIDATOR_ID, ValidatorCatalog
from server.core.kernel.domain.node import NodeKind
from server.core.kernel.infrastructure.agent_executor import AgentPoolExecutor
from server.core.kernel.validators.code_validator import CodeArtifactValidator
from server.core.kernel.validators.model3d_validator import Model3DArtifactValidator
from server.core.reasoning.self_critique import CriticGate, LanguageCritic, self_critique_engine
from server.features.self_healing_coder.sandbox_runner import sandbox_gateway


def build_validator_catalog() -> ValidatorCatalog:
    code = CodeArtifactValidator(sandbox_gateway)
    gate = CriticGate(
        deterministic={
            NodeKind.CODE: code,
            NodeKind.TOOL_SYNTHESIS: code,
            NodeKind.PARAMETRIC: Model3DArtifactValidator(),
        },
        language_critic=LanguageCritic(self_critique_engine),
    )
    catalog = ValidatorCatalog()
    catalog.register(DEFAULT_VALIDATOR_ID, gate)
    return catalog


validator_catalog = build_validator_catalog()


def build_scheduler(
    pool: AgentPoolManager,
    user_id: str,
    device_id: str,
    goal: str,
    observer: Optional[RunObserver] = None,
    checkpoint: Optional[Checkpoint] = None,
    consensus: Optional[ConsensusPort] = None,
) -> DagScheduler:
    executor = AgentPoolExecutor(pool, user_id, device_id, goal)
    return DagScheduler(executor, validator_catalog, consensus=consensus, observer=observer, checkpoint=checkpoint)
