import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

import httpx

from sandbox_broker.config import BrokerConfig
from sandbox_broker.engine import Engine
from sandbox_broker.registry import BackendRegistry
from sandbox_broker.server import bind_handler
from server.features.sandbox.application.gateway import SandboxGateway
from server.features.sandbox.domain.errors import SandboxRejectedError, SandboxUnavailableError, SpecError
from server.features.sandbox.domain.report import ExecutionReport
from server.features.sandbox.domain.strength import Strength
from server.features.sandbox.infrastructure.broker_client import BrokerClient
from server.features.self_healing_coder.sandbox_runner import SandboxRunner
from server.tests.test_sandbox_broker import FakeBackend

KEY = "a1" * 32


class BrokerOverHttp:
    def __init__(self, backend, key=KEY, clock=None):
        self.root = tempfile.TemporaryDirectory()
        config = BrokerConfig(work_dir=self.root.name, queue_wait_seconds=1, max_concurrent=2)
        registry = BackendRegistry([backend])
        handler = bind_handler(Engine(config, registry, None), registry, lambda: key, 1 << 20, **({"clock": clock} if clock else {}))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.root.cleanup()

    def client(self, key=KEY, clock=None):
        kwargs = {"clock": clock} if clock else {}
        return BrokerClient("", lambda: key, base_url=f"http://127.0.0.1:{self.server.server_port}", transport=httpx.AsyncHTTPTransport(), **kwargs)


class BrokerRoundTripTest(unittest.IsolatedAsyncioTestCase):
    async def test_python_execution_returns_report_and_artifacts(self):
        backend = FakeBackend("container", Strength.CONTAINER, writes={"out.txt": b"result"})
        with BrokerOverHttp(backend) as broker:
            report = await SandboxGateway(broker.client()).run_python("print('hi')")
        self.assertTrue(report.succeeded)
        self.assertEqual(report.backend, "container")
        self.assertEqual(report.artifacts[0].content, b"result")

    async def test_wrong_key_is_rejected(self):
        with BrokerOverHttp(FakeBackend("c", Strength.CONTAINER)) as broker:
            with self.assertRaises(SandboxRejectedError):
                await SandboxGateway(broker.client(key="b2" * 32)).run_python("print(1)")

    async def test_replayed_old_request_is_rejected(self):
        with BrokerOverHttp(FakeBackend("c", Strength.CONTAINER)) as broker:
            with self.assertRaises(SandboxRejectedError):
                await SandboxGateway(broker.client(clock=lambda: 1000.0)).run_python("print(1)")

    async def test_invalid_spec_is_a_client_error_and_backend_untouched(self):
        backend = FakeBackend("c", Strength.CONTAINER)
        with BrokerOverHttp(backend) as broker:
            client = broker.client()
            with self.assertRaises(SpecError):
                await SandboxGateway(client).run_python(" ")
            self.assertEqual(backend.calls, 0)

    async def test_strength_requirement_is_enforced_before_execution(self):
        backend = FakeBackend("c", Strength.CONTAINER)
        with BrokerOverHttp(backend) as broker:
            with self.assertRaises(SandboxUnavailableError):
                await SandboxGateway(broker.client()).run_python("print(1)", min_strength=Strength.USERSPACE_KERNEL)
            self.assertEqual(backend.calls, 0)

    async def test_status_reports_backends(self):
        with BrokerOverHttp(FakeBackend("c", Strength.CONTAINER)) as broker:
            status = await broker.client().status()
        self.assertTrue(status["ready"])
        self.assertEqual(status["backends"][0]["name"], "c")

    async def test_unreachable_broker_maps_to_unavailable(self):
        client = BrokerClient("", lambda: KEY, base_url="http://127.0.0.1:1", transport=httpx.AsyncHTTPTransport())
        with self.assertRaises(SandboxUnavailableError):
            await SandboxGateway(client).run_python("print(1)")


class FixedPort:
    def __init__(self, report=None, error=None):
        self.report, self.error = report, error

    async def execute(self, spec):
        if self.error:
            raise self.error
        return self.report


def report(**overrides):
    values = dict(exit_code=0, stdout="out", stderr="", timed_out=False, oom_killed=False, backend="c", strength=1)
    values.update(overrides)
    return ExecutionReport(**values)


class GatewayTest(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_report_weaker_than_required(self):
        gateway = SandboxGateway(FixedPort(report(strength=1)))
        with self.assertRaises(SandboxRejectedError):
            await gateway.run_python("print(1)", min_strength=Strength.USERSPACE_KERNEL)

    async def test_bash_uses_bash_language(self):
        captured = {}

        class Capture:
            async def execute(self, spec):
                captured["language"] = spec.language.value
                return report()

        await SandboxGateway(Capture()).run_bash("echo hi")
        self.assertEqual(captured["language"], "bash")


class RunnerAdapterTest(unittest.IsolatedAsyncioTestCase):
    async def run_with(self, port):
        return await SandboxRunner(SandboxGateway(port), 5).execute_in_sandbox("print(1)")

    async def test_success_maps_to_tuple(self):
        self.assertEqual(await self.run_with(FixedPort(report())), (True, "out", ""))

    async def test_failure_exposes_stderr_for_self_healing(self):
        ok, _, stderr = await self.run_with(FixedPort(report(exit_code=1, stderr="Traceback: NameError")))
        self.assertFalse(ok)
        self.assertIn("NameError", stderr)

    async def test_timeout_is_reported_as_failure(self):
        ok, _, stderr = await self.run_with(FixedPort(report(exit_code=137, timed_out=True)))
        self.assertFalse(ok)
        self.assertIn("exceeded 5s", stderr)

    async def test_unavailable_sandbox_is_a_failure_not_an_exception(self):
        ok, stdout, stderr = await self.run_with(FixedPort(error=SandboxUnavailableError("down")))
        self.assertEqual((ok, stdout), (False, ""))
        self.assertIn("down", stderr)


if __name__ == "__main__":
    unittest.main()
