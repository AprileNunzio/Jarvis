import json
import os
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

from server.core.orchestrator import brain_routing
from server.features.llm_gateway import gateway as gateway_module
from server.features.llm_gateway.contracts import LLMMessage, LLMRequest
from server.features.llm_gateway.supervisor_bridge import BridgeError, SupervisorBridge, is_remote_ref, sign

KNOWN_KEY = "k" * 64
KNOWN_SIGNATURE = sign(KNOWN_KEY, "POST", "/api/internal/brain/complete", 1700000000, b'{"a":1}')


class RoutesFileTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = os.path.join(self.temp.name, "routes.json")
        patcher = patch.object(brain_routing.settings, "BRAIN_ROUTES_PATH", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        brain_routing._cache = (-1, {})

    def write(self, data):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        os.utime(self.path, ns=(time.time_ns(), time.time_ns()))

    def test_published_chain_wins_and_follows_file_changes(self):
        self.write({"components": {"research": ["cloud:s1/m", "qwen:7b"]}, "explicit": ["research"],
                    "keep_alive": {"qwen:7b": "1h"}})
        self.assertEqual(brain_routing.brain_order_for("research"), ["cloud:s1/m", "qwen:7b"])
        self.assertTrue(brain_routing.has_explicit_brain("research"))
        self.assertEqual(brain_routing.keep_alive_for("qwen:7b", "5m"), "1h")
        self.assertEqual(brain_routing.keep_alive_for("other", "5m"), "5m")
        self.write({"components": {"research": ["x"]}})
        self.assertEqual(brain_routing.brain_order_for("research"), ["x"])

    def test_missing_or_corrupt_file_falls_back_to_the_environment(self):
        with patch.object(brain_routing.settings, "JARVIS_LLM_RICERCATORE_ORDER", "a, b"):
            self.assertEqual(brain_routing.brain_order_for("research"), ["a", "b"])
            with open(self.path, "w", encoding="utf-8") as handle:
                handle.write("{broken")
            brain_routing._cache = (-1, {})
            self.assertEqual(brain_routing.brain_order_for("research"), ["a", "b"])
        self.assertEqual(brain_routing.brain_order_for("unknown"), [])
        self.assertFalse(brain_routing.has_explicit_brain("research"))


class SigningTest(unittest.TestCase):
    def test_signature_is_stable_and_binds_every_field(self):
        self.assertEqual(KNOWN_SIGNATURE, sign(KNOWN_KEY, "POST", "/api/internal/brain/complete", 1700000000, b'{"a":1}'))
        for variant in (sign("j" * 64, "POST", "/api/internal/brain/complete", 1700000000, b'{"a":1}'),
                        sign(KNOWN_KEY, "GET", "/api/internal/brain/complete", 1700000000, b'{"a":1}'),
                        sign(KNOWN_KEY, "POST", "/other", 1700000000, b'{"a":1}'),
                        sign(KNOWN_KEY, "POST", "/api/internal/brain/complete", 1700000001, b'{"a":1}'),
                        sign(KNOWN_KEY, "POST", "/api/internal/brain/complete", 1700000000, b'{"a":2}')):
            self.assertNotEqual(KNOWN_SIGNATURE, variant)

    def test_remote_refs(self):
        self.assertTrue(is_remote_ref("cloud:openai/gpt"))
        self.assertFalse(is_remote_ref("qwen2.5:3b"))

    def test_headers_carry_timestamp_and_signature(self):
        headers = SupervisorBridge("http://x", lambda: KNOWN_KEY)._headers("/p", b"{}")
        self.assertTrue(abs(int(headers["X-Jarvis-Timestamp"]) - time.time()) < 5)
        self.assertEqual(headers["X-Jarvis-Signature"], sign(KNOWN_KEY, "POST", "/p", int(headers["X-Jarvis-Timestamp"]), b"{}"))


class GatewayRoutingTest(unittest.IsolatedAsyncioTestCase):
    def request(self, **kwargs):
        return LLMRequest(model_name="default", messages=[LLMMessage(role="user", content="ciao")], **kwargs)

    async def test_remote_refs_go_through_the_supervisor_and_are_traced(self):
        events = []

        async def report(op, call, **fields):
            events.append((op, fields.get("ref") or fields.get("component")))

        with patch.object(gateway_module.bridge, "complete", AsyncMock(return_value={"text": "risposta", "tokens": 3})), \
                patch.object(gateway_module.bridge, "report", report):
            reply = await gateway_module.llm_gateway.generate_completion(
                self.request(models=["cloud:s1/big"], component="kernel_critic"))
        self.assertEqual((reply.content, reply.model_used), ("risposta", "cloud:s1/big"))
        self.assertEqual([e[0] for e in events], ["begin", "attempt", "done"])
        self.assertEqual(events[0][1], "kernel_critic")

    async def test_component_without_explicit_models_uses_published_chain(self):
        with patch.object(gateway_module, "brain_order_for", return_value=["cloud:s1/a", "cloud:s2/b"]), \
                patch.object(gateway_module.bridge, "complete", AsyncMock(side_effect=[BridgeError("down"), {"text": "ok"}])) as complete, \
                patch.object(gateway_module.bridge, "report", AsyncMock()):
            reply = await gateway_module.llm_gateway.generate_completion(self.request(component="research"))
        self.assertEqual((reply.content, reply.model_used), ("ok", "cloud:s2/b"))
        self.assertEqual(complete.await_count, 2)

    async def test_requests_without_component_are_not_traced_by_the_core(self):
        report = AsyncMock()
        with patch.object(gateway_module.bridge, "complete", AsyncMock(return_value={"text": "ok"})), \
                patch.object(gateway_module.bridge, "report", report):
            await gateway_module.llm_gateway.generate_completion(self.request(models=["cloud:s1/x"]))
        report.assert_not_awaited()

    async def test_everything_failing_ends_in_the_marked_synthetic_answer(self):
        with patch.object(gateway_module.bridge, "complete", AsyncMock(side_effect=BridgeError("down"))), \
                patch.object(gateway_module.bridge, "report", AsyncMock()) as report:
            reply = await gateway_module.llm_gateway.generate_completion(
                self.request(models=["cloud:s1/x"], component="research"))
        self.assertTrue(reply.is_synthetic)
        self.assertEqual(report.await_args_list[-1].args[0], "abort")


if __name__ == "__main__":
    unittest.main()
