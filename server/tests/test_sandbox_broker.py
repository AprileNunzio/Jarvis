import os
import tempfile
import unittest

from sandbox_broker.backends import Backend, RawResult
from sandbox_broker.collector import collect
from sandbox_broker.config import BrokerConfig
from sandbox_broker.docker_cmd import build_run_argv
from sandbox_broker.engine import Engine
from sandbox_broker.housekeeping import remove_stale_workspaces
from sandbox_broker.registry import BackendRegistry
from sandbox_broker.workspace import Workspace
from server.features.sandbox.domain.errors import SandboxUnavailableError
from server.features.sandbox.domain.spec import ExecutionSpec, Language, ResourceLimits
from server.features.sandbox.domain.strength import Strength


class FakeBackend(Backend):
    def __init__(self, name, strength, ready=True, result=None, writes=None):
        self.name = name
        self.strength = strength
        self._ready = ready
        self._result = result or RawResult(0, b"ok", b"", False, False, 5)
        self._writes = writes or {}
        self.calls = 0

    def available(self):
        return self._ready

    def refresh(self):
        return None

    def run(self, spec, workspace):
        self.calls += 1
        for name, content in self._writes.items():
            with open(os.path.join(workspace.out_dir, name), "wb") as handle:
                handle.write(content)
        return self._result


def spec(**overrides):
    values = {"language": Language.PYTHON, "source": "print(1)"}
    values.update(overrides)
    return ExecutionSpec(**values)


class DockerCommandTest(unittest.TestCase):
    def argv(self, runtime=None, **overrides):
        return build_run_argv("docker", "c1", "img", spec(**overrides), "/w/in", "/w/out", 65534, runtime)

    def test_isolation_flags_are_always_present(self):
        argv = self.argv()
        joined = " ".join(argv)
        for fragment in (
            "--network none", "--read-only", "--cap-drop ALL", "--security-opt no-new-privileges",
            "--user 65534:65534", "--rm", "--volume /w/in:/in:ro", "--volume /w/out:/out:rw",
        ):
            self.assertIn(fragment, joined)

    def test_limits_are_applied(self):
        argv = self.argv(limits=ResourceLimits(memory_mb=256, cpus=1.5, pids=32, output_bytes=2048))
        joined = " ".join(argv)
        self.assertIn("--memory 256m", joined)
        self.assertIn("--memory-swap 256m", joined)
        self.assertIn("--cpus 1.5", joined)
        self.assertIn("--pids-limit 32", joined)
        self.assertIn("--ulimit fsize=2048", joined)

    def test_runtime_flag_only_when_requested(self):
        self.assertNotIn("--runtime", self.argv())
        argv = self.argv(runtime="runsc")
        self.assertEqual(argv[argv.index("--runtime") + 1], "runsc")

    def test_no_host_mounts_besides_workspace_and_no_shell_interpolation(self):
        argv = self.argv(source="$(rm -rf /); `id`")
        self.assertEqual([a for a in argv if a == "--volume"].__len__(), 2)
        self.assertNotIn("$(rm -rf /); `id`", argv)
        self.assertEqual(argv[-4:], ["python", "-I", "-B", "/in/main.py"])

    def test_bash_entrypoint(self):
        self.assertEqual(self.argv(language=Language.BASH)[-4:], ["bash", "--noprofile", "--norc", "/in/main.sh"])


class WorkspaceTest(unittest.TestCase):
    def test_materialises_source_and_inputs_then_cleans_up(self):
        with tempfile.TemporaryDirectory() as root:
            with Workspace(root, spec(inputs={"d.txt": b"data"}), None) as workspace:
                with open(os.path.join(workspace.in_dir, "main.py"), encoding="utf-8") as handle:
                    self.assertEqual(handle.read(), "print(1)")
                with open(os.path.join(workspace.in_dir, "d.txt"), "rb") as handle:
                    self.assertEqual(handle.read(), b"data")
                self.assertTrue(os.path.isdir(workspace.out_dir))
                path = workspace.path
            self.assertFalse(os.path.exists(path))

    def test_cleans_up_even_when_body_raises(self):
        with tempfile.TemporaryDirectory() as root:
            path = ""
            with self.assertRaises(RuntimeError):
                with Workspace(root, spec(), None) as workspace:
                    path = workspace.path
                    raise RuntimeError("boom")
            self.assertFalse(os.path.exists(path))

    def test_stale_workspaces_are_swept(self):
        with tempfile.TemporaryDirectory() as root:
            old = os.path.join(root, "job-old")
            os.mkdir(old)
            config = BrokerConfig(work_dir=root)
            remove_stale_workspaces(config, now=os.stat(old).st_mtime + 7200)
            self.assertFalse(os.path.exists(old))
            fresh = os.path.join(root, "job-new")
            os.mkdir(fresh)
            remove_stale_workspaces(config, now=os.stat(fresh).st_mtime + 10)
            self.assertTrue(os.path.exists(fresh))


class CollectorTest(unittest.TestCase):
    def write(self, root, name, content=b"x"):
        with open(os.path.join(root, name), "wb") as handle:
            handle.write(content)

    def test_collects_regular_files(self):
        with tempfile.TemporaryDirectory() as out:
            self.write(out, "a.txt", b"hello")
            artifacts, truncated = collect(out, ResourceLimits())
            self.assertEqual([(a.name, a.content) for a in artifacts], [("a.txt", b"hello")])
            self.assertFalse(truncated)

    def test_skips_directories_and_invalid_names(self):
        with tempfile.TemporaryDirectory() as out:
            os.mkdir(os.path.join(out, "sub"))
            self.write(out, ".hidden")
            self.write(out, "ok.txt")
            artifacts, truncated = collect(out, ResourceLimits())
            self.assertEqual([a.name for a in artifacts], ["ok.txt"])
            self.assertTrue(truncated)

    def test_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as out, tempfile.TemporaryDirectory() as secret:
            target = os.path.join(secret, "secret.txt")
            self.write(secret, "secret.txt", b"top secret")
            try:
                os.symlink(target, os.path.join(out, "link.txt"))
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            artifacts, truncated = collect(out, ResourceLimits())
            self.assertEqual(artifacts, ())
            self.assertTrue(truncated)

    def test_enforces_total_size(self):
        with tempfile.TemporaryDirectory() as out:
            self.write(out, "a.bin", b"a" * 800)
            self.write(out, "b.bin", b"b" * 800)
            artifacts, truncated = collect(out, ResourceLimits(output_bytes=1024))
            self.assertEqual([a.name for a in artifacts], ["a.bin"])
            self.assertTrue(truncated)


class RegistryTest(unittest.TestCase):
    def test_prefers_strongest_available_backend(self):
        registry = BackendRegistry([FakeBackend("c", Strength.CONTAINER), FakeBackend("g", Strength.USERSPACE_KERNEL)])
        self.assertEqual(registry.select(Strength.CONTAINER).name, "g")

    def test_falls_back_when_strong_backend_is_down(self):
        registry = BackendRegistry([FakeBackend("c", Strength.CONTAINER), FakeBackend("g", Strength.USERSPACE_KERNEL, ready=False)])
        self.assertEqual(registry.select(Strength.CONTAINER).name, "c")

    def test_refuses_to_downgrade_below_minimum(self):
        registry = BackendRegistry([FakeBackend("c", Strength.CONTAINER)])
        with self.assertRaises(SandboxUnavailableError):
            registry.select(Strength.USERSPACE_KERNEL)

    def test_describe_and_readiness(self):
        registry = BackendRegistry([FakeBackend("c", Strength.CONTAINER, ready=False)])
        self.assertFalse(registry.any_available())
        self.assertEqual(registry.describe(), [{"name": "c", "strength": 1, "available": False}])


class EngineTest(unittest.TestCase):
    def engine(self, backend, root):
        config = BrokerConfig(work_dir=root, queue_wait_seconds=1, max_concurrent=1)
        return Engine(config, BackendRegistry([backend]), None)

    def test_builds_report_with_artifacts(self):
        with tempfile.TemporaryDirectory() as root:
            backend = FakeBackend("c", Strength.CONTAINER, writes={"model.obj": b"v 0 0 0"})
            report = self.engine(backend, root).execute(spec())
            self.assertTrue(report.succeeded)
            self.assertEqual((report.backend, report.strength, report.stdout), ("c", 1, "ok"))
            self.assertEqual([a.name for a in report.artifacts], ["model.obj"])
            self.assertEqual(os.listdir(root), [])

    def test_propagates_timeout_and_oom_flags(self):
        with tempfile.TemporaryDirectory() as root:
            backend = FakeBackend("c", Strength.CONTAINER, result=RawResult(137, b"", b"", True, False, 30000))
            report = self.engine(backend, root).execute(spec())
            self.assertTrue(report.timed_out)
            self.assertFalse(report.succeeded)

    def test_invalid_spec_never_reaches_backend(self):
        with tempfile.TemporaryDirectory() as root:
            backend = FakeBackend("c", Strength.CONTAINER)
            with self.assertRaises(ValueError):
                self.engine(backend, root).execute(spec(source=""))
            self.assertEqual(backend.calls, 0)

    def test_no_backend_meeting_minimum_does_not_run_anything(self):
        with tempfile.TemporaryDirectory() as root:
            backend = FakeBackend("c", Strength.CONTAINER)
            with self.assertRaises(SandboxUnavailableError):
                self.engine(backend, root).execute(spec(min_strength=Strength.MICROVM))
            self.assertEqual(backend.calls, 0)

    def test_busy_engine_rejects_instead_of_queueing_forever(self):
        with tempfile.TemporaryDirectory() as root:
            engine = self.engine(FakeBackend("c", Strength.CONTAINER), root)
            engine._slots.acquire()
            with self.assertRaises(SandboxUnavailableError):
                engine.execute(spec())


if __name__ == "__main__":
    unittest.main()
