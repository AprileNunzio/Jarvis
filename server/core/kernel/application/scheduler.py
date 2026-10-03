import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional

from server.core.kernel.application.ports import (
    Checkpoint,
    ConsensusPort,
    NodeExecutor,
    RunObserver,
    ValidatorRegistry,
)
from server.core.kernel.application.run_state import DagRun
from server.core.kernel.domain.dag import ExecutionDag
from server.core.kernel.domain.node import NodeSpec, NodeState, RiskLevel
from server.core.kernel.domain.outcome import ErrorPayload

logger = logging.getLogger("jarvis.kernel.scheduler")


@dataclass(frozen=True)
class DagOutcome:
    status: str
    run: DagRun

    @property
    def succeeded(self) -> bool:
        return self.status == "COMPLETED"

    def summary(self) -> Dict[str, str]:
        return {node_id: node.state.value for node_id, node in self.run.nodes.items()}


class DagScheduler:
    def __init__(
        self,
        executor: NodeExecutor,
        validators: ValidatorRegistry,
        consensus: Optional[ConsensusPort] = None,
        observer: Optional[RunObserver] = None,
        checkpoint: Optional[Checkpoint] = None,
        max_parallel: int = 2,
        clock=time.monotonic,
    ) -> None:
        self._executor = executor
        self._validators = validators
        self._consensus = consensus
        self._observer = observer
        self._checkpoint = checkpoint
        self._slots = asyncio.Semaphore(max_parallel)
        self._clock = clock

    async def run(self, dag: ExecutionDag) -> DagOutcome:
        run = DagRun(dag)
        if not await self._authorise(run):
            return DagOutcome("REJECTED", run)
        return await self.resume(run)

    async def resume(self, run: DagRun) -> DagOutcome:
        for wave in run.dag.waves():
            if self._checkpoint:
                await self._checkpoint.wait_if_paused()
            pending = [n for n in wave if run.state_of(n) is NodeState.PENDING]
            await asyncio.gather(*(self._run_node(run, n) for n in pending))
        return DagOutcome("COMPLETED" if run.succeeded() else "FAILED", run)

    async def _authorise(self, run: DagRun) -> bool:
        if run.dag.max_risk() < RiskLevel.DESTRUCTIVE:
            return True
        for node_id, spec in run.dag.nodes.items():
            if spec.risk is RiskLevel.DESTRUCTIVE:
                await self._move(run, node_id, NodeState.BLOCKED_ON_CONSENSUS)
        approved = False
        if self._consensus is not None:
            verdict = await self._consensus.vote(run.dag)
            approved = verdict.approved
            if not approved:
                logger.warning("consensus rejected dag %s: %s", run.dag.fingerprint()[:12], verdict.objections)
        if approved:
            for node_id in run.dag.nodes:
                if run.state_of(node_id) is NodeState.BLOCKED_ON_CONSENSUS:
                    await self._move(run, node_id, NodeState.PENDING)
            return True
        for node_id in run.dag.nodes:
            await self._move(run, node_id, NodeState.REJECTED)
        return False

    async def _run_node(self, run: DagRun, node_id: str) -> None:
        spec = run.dag.nodes[node_id]
        blocker = self._failed_upstream(run, spec)
        if blocker:
            run.nodes[node_id].error = ErrorPayload("upstream_failed", f"dependency {blocker} did not complete")
            await self._move(run, node_id, NodeState.SKIPPED)
            return
        async with self._slots:
            await self._attempt_until_accepted(run, spec)

    @staticmethod
    def _failed_upstream(run: DagRun, spec: NodeSpec) -> Optional[str]:
        for dep in spec.depends_on:
            if run.state_of(dep) is not NodeState.ACCEPTED:
                return dep
        return None

    async def _attempt_until_accepted(self, run: DagRun, spec: NodeSpec) -> None:
        node = run.nodes[spec.node_id]
        deadline = self._clock() + spec.retry.deadline_seconds
        feedback: Optional[ErrorPayload] = None
        while node.attempts < spec.retry.max_attempts:
            remaining = deadline - self._clock()
            if remaining <= 0:
                node.error = ErrorPayload("deadline", f"node exceeded {spec.retry.deadline_seconds:g}s")
                break
            node.attempts += 1
            await self._move(run, spec.node_id, NodeState.RUNNING)
            feedback = await self._attempt(run, spec, feedback, remaining)
            if feedback is None:
                await self._move(run, spec.node_id, NodeState.ACCEPTED)
                return
            node.error = feedback
            await self._move(run, spec.node_id, NodeState.HEALING)
        await self._move(run, spec.node_id, NodeState.FAILED)

    async def _attempt(
        self, run: DagRun, spec: NodeSpec, feedback: Optional[ErrorPayload], budget: float
    ) -> Optional[ErrorPayload]:
        node = run.nodes[spec.node_id]
        try:
            result = await asyncio.wait_for(self._executor.execute(spec, run.accepted_results(), feedback), budget)
        except asyncio.TimeoutError:
            return ErrorPayload("timeout", f"execution exceeded the remaining {budget:.0f}s budget")
        except Exception as exc:
            logger.warning("node %s raised %s", spec.node_id, exc.__class__.__name__)
            return ErrorPayload("exception", f"{exc.__class__.__name__}: {exc}")
        await self._move(run, spec.node_id, NodeState.VALIDATING)
        try:
            verdict = await self._validators.resolve(spec.validator_id).judge(spec, result)
        except Exception as exc:
            return ErrorPayload("validator_failure", f"{exc.__class__.__name__}: {exc}")
        if not verdict.accepted:
            return verdict.error or ErrorPayload("rejected", "validator rejected the result")
        node.result = result
        node.error = None
        return None

    async def _move(self, run: DagRun, node_id: str, state: NodeState) -> None:
        run.nodes[node_id].move(state)
        if self._observer:
            await self._observer.on_transition(node_id, state, run.completed_count(), len(run.nodes))
