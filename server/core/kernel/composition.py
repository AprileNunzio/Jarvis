from typing import Optional

from server.core.agent_registry.pool_manager import AgentPoolManager
from server.core.kernel.application.ports import Checkpoint, ConsensusPort, RunObserver
from server.core.kernel.application.scheduler import DagScheduler
from server.core.kernel.application.validators import ValidatorCatalog
from server.core.kernel.infrastructure.agent_executor import AgentPoolExecutor

validator_catalog = ValidatorCatalog()


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
