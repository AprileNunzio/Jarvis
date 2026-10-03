import asyncio
import json
import tempfile
import unittest

from sandbox_broker.selfcheck import PROBE_SOURCE, evaluate
from server.core.kernel.application.scheduler import DagScheduler
from server.core.kernel.application.validators import ValidatorCatalog
from server.core.kernel.domain.dag import ExecutionDag
from server.core.kernel.domain.node import NodeKind, NodeSpec
from server.core.kernel.domain.outcome import NodeResult
from server.core.orchestrator.interrupt_manager import LongRunningTaskManager
from server.features.sandbox.domain.report import Artifact, ExecutionReport


class InstantExecutor:
    async def execute(self, spec, upstream, feedback):
        return NodeResult(spec.node_id, {"status": "SUCCESS"}, "ok")


def dag(count):
    specs = [NodeSpec(f"n{i}", NodeKind.REASONING, f"step {i}", (f"n{i - 1}",) if i else ()) for i in range(count)]
    return ExecutionDag.build(specs)


def read_state(manager, task_id):
    return json.loads((manager.state_dir / f"{task_id}.json").read_text(encoding="utf-8"))


class ProjectManagerTest(unittest.IsolatedAsyncioTestCase):
    async def test_work_is_really_executed_and_progress_reported(self):
        with tempfile.TemporaryDirectory() as root:
            manager = LongRunningTaskManager(root)
            ran = []

            async def work(checkpoint, observer):
                outcome = await DagScheduler(InstantExecutor(), ValidatorCatalog(), observer=observer, checkpoint=checkpoint).run(dag(3))
                ran.append(outcome.status)
                return outcome.succeeded

            await manager.start_project("p1", "demo", work)
            await manager.active_tasks["p1"].task
            self.assertEqual(ran, ["COMPLETED"])
            self.assertEqual(read_state(manager, "p1"), {"status": "completed", "progress": 100, "name": "demo"})
            self.assertEqual(manager.active_tasks, {})

    async def test_failed_work_is_recorded_as_error(self):
        with tempfile.TemporaryDirectory() as root:
            manager = LongRunningTaskManager(root)

            async def work(checkpoint, observer):
                return False

            await manager.start_project("p2", "bad", work)
            await asyncio.sleep(0.05)
            self.assertEqual(read_state(manager, "p2")["status"], "error")

    async def test_exception_is_contained(self):
        with tempfile.TemporaryDirectory() as root:
            manager = LongRunningTaskManager(root)

            async def work(checkpoint, observer):
                raise RuntimeError("boom")

            await manager.start_project("p3", "boom", work)
            await asyncio.sleep(0.05)
            self.assertEqual(read_state(manager, "p3")["status"], "error")

    async def test_pause_blocks_the_next_wave_until_resumed(self):
        with tempfile.TemporaryDirectory() as root:
            manager = LongRunningTaskManager(root)
            started = asyncio.Event()

            async def work(checkpoint, observer):
                started.set()
                await asyncio.sleep(0.01)
                outcome = await DagScheduler(InstantExecutor(), ValidatorCatalog(), observer=observer, checkpoint=checkpoint).run(dag(2))
                return outcome.succeeded

            await manager.start_project("p4", "pausable", work)
            self.assertTrue(manager.pause_project("p4"))
            await started.wait()
            await asyncio.sleep(0.1)
            self.assertFalse(manager.active_tasks["p4"].task.done())
            self.assertEqual(read_state(manager, "p4")["status"], "paused")
            self.assertTrue(manager.resume_project("p4"))
            await asyncio.wait_for(manager.active_tasks["p4"].task, 2)
            self.assertEqual(read_state(manager, "p4")["status"], "completed")

    async def test_pause_and_resume_unknown_project(self):
        with tempfile.TemporaryDirectory() as root:
            manager = LongRunningTaskManager(root)
            self.assertFalse(manager.pause_project("ghost"))
            self.assertFalse(manager.resume_project("ghost"))

    def test_unfinished_projects_are_marked_interrupted_on_boot(self):
        with tempfile.TemporaryDirectory() as root:
            manager = LongRunningTaskManager(root)
            (manager.state_dir / "a.json").write_text(json.dumps({"status": "running", "progress": 30, "name": "a"}))
            (manager.state_dir / "b.json").write_text(json.dumps({"status": "completed", "progress": 100, "name": "b"}))
            self.assertEqual(manager.mark_interrupted_projects(), 1)
            self.assertEqual(read_state(manager, "a")["status"], "interrupted")
            self.assertEqual(read_state(manager, "b")["status"], "completed")


def report(stdout, **overrides):
    values = dict(exit_code=0, stdout=stdout, stderr="", timed_out=False, oom_killed=False, backend="gvisor", strength=2,
                  artifacts=(Artifact("proof.txt", b"artifact"),))
    values.update(overrides)
    return ExecutionReport(**values)


GOOD = json.dumps({"uid": 65534, "network": "blocked", "rootfs": "readonly", "docker_socket": False, "host_config": False})


class SelfcheckEvaluationTest(unittest.TestCase):
    def test_probe_source_compiles(self):
        compile(PROBE_SOURCE, "probe", "exec")

    def test_healthy_sandbox_passes(self):
        outcome = evaluate(report(GOOD))
        self.assertTrue(outcome["ok"])
        self.assertEqual(outcome["backend"], "gvisor")

    def test_each_isolation_failure_is_detected(self):
        for key, value in (("network", "open"), ("rootfs", "writable"), ("docker_socket", True), ("host_config", True), ("uid", 0)):
            observed = {**json.loads(GOOD), key: value}
            with self.subTest(key=key):
                self.assertFalse(evaluate(report(json.dumps(observed)))["ok"])

    def test_missing_artifact_or_failed_run_is_detected(self):
        self.assertFalse(evaluate(report(GOOD, artifacts=()))["ok"])
        self.assertFalse(evaluate(report(GOOD, exit_code=1))["ok"])
        self.assertFalse(evaluate(report("garbage"))["ok"])


if __name__ == "__main__":
    unittest.main()
