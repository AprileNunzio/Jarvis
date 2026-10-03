import asyncio
import unittest

from server.core.kernel.application.run_state import DagRun
from server.core.kernel.application.scheduler import DagScheduler
from server.core.kernel.application.validators import ValidatorCatalog
from server.core.kernel.domain.dag import ExecutionDag
from server.core.kernel.domain.node import NodeKind, NodeSpec, NodeState, RetryPolicy, RiskLevel
from server.core.kernel.domain.outcome import ConsensusVerdict, NodeResult, Verdict


def node(node_id, *deps, **overrides):
    values = {"node_id": node_id, "kind": NodeKind.REASONING, "description": f"do {node_id}", "depends_on": tuple(deps)}
    values.update(overrides)
    return NodeSpec(**values)


class ScriptedExecutor:
    def __init__(self, behaviours=None):
        self.behaviours = behaviours or {}
        self.calls = []
        self.feedback_seen = []
        self.upstream_seen = {}

    async def execute(self, spec, upstream, feedback):
        self.calls.append(spec.node_id)
        self.feedback_seen.append((spec.node_id, feedback.kind if feedback else None))
        self.upstream_seen[spec.node_id] = sorted(upstream)
        step = self.behaviours.get(spec.node_id)
        if callable(step):
            return await step(len([c for c in self.calls if c == spec.node_id]))
        return NodeResult(spec.node_id, {"status": "SUCCESS"}, f"done {spec.node_id}")


class Recorder:
    def __init__(self):
        self.events = []

    async def on_transition(self, node_id, state, completed, total):
        self.events.append((node_id, state, completed, total))


class FixedConsensus:
    def __init__(self, approved):
        self.approved = approved
        self.votes = 0

    async def vote(self, dag):
        self.votes += 1
        return ConsensusVerdict(self.approved, () if self.approved else ("unsafe",))


def scheduler(executor, **kwargs):
    return DagScheduler(executor, ValidatorCatalog(), **kwargs)


class SchedulerHappyPathTest(unittest.IsolatedAsyncioTestCase):
    async def test_runs_every_node_in_dependency_order_and_passes_upstream(self):
        executor = ScriptedExecutor()
        dag = ExecutionDag.build([node("a"), node("b", "a"), node("c", "a"), node("d", "b", "c")])
        outcome = await scheduler(executor).run(dag)
        self.assertTrue(outcome.succeeded)
        self.assertEqual(executor.calls[0], "a")
        self.assertEqual(executor.calls[-1], "d")
        self.assertEqual(executor.upstream_seen["d"], ["a", "b", "c"])
        self.assertEqual(set(outcome.summary().values()), {"accepted"})

    async def test_state_machine_visits_validation_before_acceptance(self):
        outcome = await scheduler(ScriptedExecutor()).run(ExecutionDag.build([node("a")]))
        self.assertEqual(outcome.run.nodes["a"].history, [NodeState.RUNNING, NodeState.VALIDATING, NodeState.ACCEPTED])

    async def test_observer_receives_progress(self):
        recorder = Recorder()
        await scheduler(ScriptedExecutor(), observer=recorder).run(ExecutionDag.build([node("a"), node("b", "a")]))
        self.assertEqual(recorder.events[-1][2:], (2, 2))


class SchedulerHealingTest(unittest.IsolatedAsyncioTestCase):
    async def test_failed_attempt_is_retried_with_error_feedback(self):
        async def flaky(attempt):
            if attempt == 1:
                return NodeResult("a", {"status": "ERROR"}, "boom")
            return NodeResult("a", {"status": "SUCCESS"}, "fixed")

        executor = ScriptedExecutor({"a": flaky})
        outcome = await scheduler(executor).run(ExecutionDag.build([node("a")]))
        self.assertTrue(outcome.succeeded)
        self.assertEqual(executor.feedback_seen, [("a", None), ("a", "agent_status")])
        self.assertEqual(outcome.run.nodes["a"].attempts, 2)
        self.assertIn(NodeState.HEALING, outcome.run.nodes["a"].history)

    async def test_exception_becomes_feedback_not_a_crash(self):
        async def raises(attempt):
            if attempt == 1:
                raise RuntimeError("compile error")
            return NodeResult("a", {"status": "SUCCESS"}, "ok")

        executor = ScriptedExecutor({"a": raises})
        outcome = await scheduler(executor).run(ExecutionDag.build([node("a")]))
        self.assertTrue(outcome.succeeded)
        self.assertEqual(executor.feedback_seen[1], ("a", "exception"))

    async def test_gives_up_after_max_attempts_and_skips_dependents(self):
        async def always_bad(attempt):
            return NodeResult("a", {"status": "ERROR"}, "")

        executor = ScriptedExecutor({"a": always_bad})
        dag = ExecutionDag.build([node("a", retry=RetryPolicy(max_attempts=2)), node("b", "a"), node("c")])
        outcome = await scheduler(executor).run(dag)
        self.assertEqual(outcome.status, "FAILED")
        self.assertEqual(outcome.run.nodes["a"].state, NodeState.FAILED)
        self.assertEqual(outcome.run.nodes["a"].attempts, 2)
        self.assertEqual(outcome.run.nodes["b"].state, NodeState.SKIPPED)
        self.assertEqual(outcome.run.nodes["c"].state, NodeState.ACCEPTED)
        self.assertNotIn("b", executor.calls)

    async def test_empty_result_is_never_accepted(self):
        async def empty(attempt):
            return NodeResult("a", {"status": "SUCCESS"}, "   ")

        outcome = await scheduler(ScriptedExecutor({"a": empty})).run(ExecutionDag.build([node("a", retry=RetryPolicy(max_attempts=1))]))
        self.assertEqual(outcome.run.nodes["a"].state, NodeState.FAILED)
        self.assertEqual(outcome.run.nodes["a"].error.kind, "empty_result")

    async def test_timeout_counts_as_a_failed_attempt(self):
        async def hang(attempt):
            await asyncio.sleep(5)

        dag = ExecutionDag.build([node("a", retry=RetryPolicy(max_attempts=1, deadline_seconds=0.05))])
        outcome = await scheduler(ScriptedExecutor({"a": hang})).run(dag)
        self.assertEqual(outcome.run.nodes["a"].state, NodeState.FAILED)
        self.assertEqual(outcome.run.nodes["a"].error.kind, "timeout")

    async def test_unknown_validator_fails_closed(self):
        outcome = await scheduler(ScriptedExecutor()).run(
            ExecutionDag.build([node("a", validator_id="nonexistent", retry=RetryPolicy(max_attempts=1))])
        )
        self.assertEqual(outcome.run.nodes["a"].state, NodeState.FAILED)
        self.assertEqual(outcome.run.nodes["a"].error.kind, "validator_failure")

    async def test_custom_validator_can_veto(self):
        class Veto:
            async def judge(self, spec, result):
                return Verdict.reject("syntax", "invalid .obj")

        catalog = ValidatorCatalog()
        catalog.register("obj", Veto())
        dag = ExecutionDag.build([node("a", validator_id="obj", retry=RetryPolicy(max_attempts=2))])
        outcome = await DagScheduler(ScriptedExecutor(), catalog).run(dag)
        self.assertEqual(outcome.run.nodes["a"].state, NodeState.FAILED)
        self.assertEqual(outcome.run.nodes["a"].error.message, "invalid .obj")


class SchedulerConsensusTest(unittest.IsolatedAsyncioTestCase):
    destructive = staticmethod(lambda: ExecutionDag.build([node("a"), node("b", "a", risk=RiskLevel.DESTRUCTIVE)]))

    async def test_destructive_dag_without_consensus_is_refused_and_nothing_runs(self):
        executor = ScriptedExecutor()
        outcome = await scheduler(executor).run(self.destructive())
        self.assertEqual(outcome.status, "REJECTED")
        self.assertEqual(executor.calls, [])
        self.assertEqual(set(outcome.summary().values()), {"rejected"})

    async def test_rejecting_consensus_blocks_execution(self):
        executor = ScriptedExecutor()
        consensus = FixedConsensus(False)
        outcome = await scheduler(executor, consensus=consensus).run(self.destructive())
        self.assertEqual((outcome.status, consensus.votes, executor.calls), ("REJECTED", 1, []))

    async def test_approving_consensus_allows_execution(self):
        executor = ScriptedExecutor()
        outcome = await scheduler(executor, consensus=FixedConsensus(True)).run(self.destructive())
        self.assertTrue(outcome.succeeded)
        self.assertIn(NodeState.BLOCKED_ON_CONSENSUS, outcome.run.nodes["b"].history)

    async def test_safe_dag_never_asks_for_consensus(self):
        consensus = FixedConsensus(False)
        outcome = await scheduler(ScriptedExecutor(), consensus=consensus).run(ExecutionDag.build([node("a")]))
        self.assertTrue(outcome.succeeded)
        self.assertEqual(consensus.votes, 0)


class SchedulerConcurrencyAndInvalidationTest(unittest.IsolatedAsyncioTestCase):
    async def test_parallelism_is_bounded(self):
        running, peak = 0, 0

        async def work(attempt):
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.02)
            running -= 1
            return NodeResult("x", {"status": "SUCCESS"}, "ok")

        dag = ExecutionDag.build([node(f"n{i}") for i in range(6)])
        executor = ScriptedExecutor({f"n{i}": work for i in range(6)})
        await scheduler(executor, max_parallel=2).run(dag)
        self.assertEqual(peak, 2)

    async def test_pause_checkpoint_is_awaited_between_waves(self):
        class Gate:
            def __init__(self):
                self.waits = 0

            async def wait_if_paused(self):
                self.waits += 1

        gate = Gate()
        await scheduler(ScriptedExecutor(), checkpoint=gate).run(ExecutionDag.build([node("a"), node("b", "a")]))
        self.assertEqual(gate.waits, 2)

    async def test_invalidating_a_node_resets_it_and_its_dependents_then_resume_reruns_only_them(self):
        executor = ScriptedExecutor()
        sched = scheduler(executor)
        dag = ExecutionDag.build([node("a"), node("b", "a"), node("c"), node("d", "b")])
        outcome = await sched.run(dag)
        executor.calls.clear()
        affected = outcome.run.invalidate("b")
        self.assertEqual(affected, frozenset({"b", "d"}))
        self.assertEqual(outcome.run.state_of("a"), NodeState.ACCEPTED)
        self.assertEqual(outcome.run.state_of("d"), NodeState.PENDING)
        resumed = await sched.resume(outcome.run)
        self.assertTrue(resumed.succeeded)
        self.assertEqual(sorted(executor.calls), ["b", "d"])

    def test_dag_run_counts(self):
        run = DagRun(ExecutionDag.build([node("a")]))
        self.assertFalse(run.is_finished())
        self.assertEqual(run.completed_count(), 0)


if __name__ == "__main__":
    unittest.main()
