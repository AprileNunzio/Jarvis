import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from features.brain import assignments as model
from features.brain import routing
from features.brain.assignments import Assignment, AssignmentError
from features.brain.components import BY_ID, COMPONENTS
from features.brain.roles import BY_ID as ROLES
from features.brain.trace import Trace

ORDERS = {"chat": ["fast"], "deep": ["big", "mid"], "coder": ["code"], "ricercatore": ["web"]}


class RegistryTest(unittest.TestCase):
    def test_every_component_defaults_to_a_known_role(self):
        for component in COMPONENTS:
            self.assertIn(component.role, ROLES, component.id)

    def test_identifiers_are_unique(self):
        self.assertEqual(len(BY_ID), len(COMPONENTS))


class ParsingTest(unittest.TestCase):
    def test_empty_assignment_is_dropped(self):
        self.assertEqual(model.parse_all({"research": {"role": "", "order": []}}), {})

    def test_order_implies_first_mode_and_is_deduplicated(self):
        parsed = model.parse_assignment({"order": ["a", "a", " b "]})
        self.assertEqual((parsed.order, parsed.mode), (("a", "b"), "first"))

    def test_rejections(self):
        bad = [{"role": "nope"}, {"order": "x"}, {"order": ["bad ref"]}, {"order": [f"m{i}" for i in range(13)]},
               {"order": ["a"], "mode": "weird"}]
        for raw in bad:
            with self.subTest(raw=raw), self.assertRaises(AssignmentError):
                model.parse_assignment(raw)
        with self.assertRaises(AssignmentError):
            model.parse_all({"ghost": {"role": "deep"}})

    def test_round_trip_and_garbage_tolerance(self):
        saved = model.dump({"research": Assignment("deep", ("x",), "only")})
        self.assertEqual(model.load(saved), {"research": Assignment("deep", ("x",), "only")})
        for junk in ("", "not json", "[]", '{"ghost":{"role":"deep"}}'):
            self.assertEqual(model.load(junk), {})


class ResolutionTest(unittest.TestCase):
    def test_default_follows_the_component_role(self):
        self.assertEqual(model.resolve("research", {}, ORDERS), ["web"])
        self.assertEqual(model.resolve("agent_self_healing_coder", {}, ORDERS), ["code"])

    def test_role_override_switches_the_inherited_list(self):
        self.assertEqual(model.resolve("research", {"research": Assignment("deep")}, ORDERS), ["big", "mid"])

    def test_first_mode_prepends_and_keeps_failover(self):
        chain = model.resolve("research", {"research": Assignment("", ("mine", "web"), "first")}, ORDERS)
        self.assertEqual(chain, ["mine", "web"])
        chain = model.resolve("analytic_reasoner", {"analytic_reasoner": Assignment("", ("mine",), "first")}, ORDERS)
        self.assertEqual(chain, ["mine", "big", "mid"])

    def test_only_mode_has_no_failover(self):
        chain = model.resolve("analytic_reasoner", {"analytic_reasoner": Assignment("", ("mine",), "only")}, ORDERS)
        self.assertEqual(chain, ["mine"])

    def test_unavailable_refs_are_filtered_out(self):
        chain = model.resolve("analytic_reasoner", {}, ORDERS, keep=lambda ref: ref != "big")
        self.assertEqual(chain, ["mid"])


class ServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.service = routing.AssignmentService(Path(self.temp.name) / "brain")
        patcher = patch.object(routing.brains, "usable", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch.object(self.service, "role_orders", return_value=ORDERS)
        patcher.start()
        self.addCleanup(patcher.stop)

    def routes(self):
        return json.loads(Path(self.temp.name, "brain", "routes.json").read_text(encoding="utf-8"))

    def test_saving_publishes_resolved_routes_for_the_core(self):
        self.service.save({"research": Assignment("", ("cloud:s1/qwen",), "first")})
        published = self.routes()
        self.assertEqual(published["components"]["research"], ["cloud:s1/qwen", "web"])
        self.assertEqual(published["components"]["kernel_critic"], ["big", "mid"])
        self.assertEqual(published["explicit"], ["research"])

    def test_clearing_returns_to_the_role(self):
        self.service.save({"research": Assignment("deep")})
        self.service.save({"research": None})
        self.assertEqual(self.service.assignments(), {})
        self.assertEqual(self.routes()["components"]["research"], ["web"])

    def test_assignments_survive_a_new_service_instance(self):
        self.service.save({"research": Assignment("", ("x",), "only")})
        again = routing.AssignmentService(Path(self.temp.name) / "brain")
        self.assertEqual(again.assignments()["research"].mode, "only")

    def test_files_are_written_atomically_without_leftovers(self):
        self.service.save({"research": Assignment("deep")})
        self.assertEqual(sorted(os.listdir(Path(self.temp.name, "brain"))), ["assignments.json", "routes.json"])


class TraceTest(unittest.TestCase):
    def test_lifecycle_moves_a_call_from_active_to_recent(self):
        trace = Trace()
        call = trace.begin("research", "ricerca", ["qwen2.5:3b"])
        trace.attempt(call, "qwen2.5:3b")
        self.assertEqual(trace.snapshot()["active"][0]["label"], "Ricercatore")
        trace.finish(call, "qwen2.5:3b", 120, "  risposta\n lunga ")
        snap = trace.snapshot()
        self.assertEqual((snap["active"], snap["recent"][0]["snippet"], snap["recent"][0]["state"]), ([], "risposta lunga", "done"))

    def test_fallback_and_failure_are_visible_in_the_steps(self):
        trace = Trace()
        call = trace.begin("research")
        trace.attempt(call, "a:1")
        trace.failed(call, "a:1", "timeout")
        trace.abort(call, "tutto spento")
        entry = trace.snapshot()["recent"][0]
        self.assertEqual(entry["state"], "failed")
        self.assertTrue(any("passo al successivo" in s["text"] for s in entry["steps"]))

    def test_sequence_number_changes_on_every_event_and_history_is_bounded(self):
        trace = Trace()
        last = trace.seq
        for _ in range(30):
            call = trace.begin("x")
            trace.finish(call, "", 1)
            self.assertGreater(trace.seq, last)
            last = trace.seq
        self.assertEqual(len(trace.snapshot()["recent"]), 14)

    def test_unknown_calls_are_ignored(self):
        trace = Trace()
        trace.attempt(99, "a")
        trace.finish(99, "a", 1)
        trace.abort(99, "x")
        self.assertEqual(trace.snapshot()["recent"], [])



class BridgeSigningTest(unittest.TestCase):
    CORE_SIGNATURE = "fbc7faccff102e01595d6f4b51a4bf83e90732582fddf532aa996050bf28f138"

    def test_supervisor_and_core_sign_identically(self):
        from features.brain import bridge
        key, path, body = "k" * 64, "/api/internal/brain/complete", b'{"a":1}'
        self.assertEqual(bridge.sign(key, "POST", path, 1700000000, body), self.CORE_SIGNATURE)
        self.assertTrue(bridge.verify(key, "POST", path, 1700000000, body, self.CORE_SIGNATURE, 1700000010))

    def test_verification_rejects_skew_wrong_key_and_zero_key(self):
        from features.brain import bridge
        key, path, body = "k" * 64, "/p", b"{}"
        good = bridge.sign(key, "POST", path, 1000, body)
        self.assertFalse(bridge.verify(key, "POST", path, 1000, body, good, 1100))
        self.assertFalse(bridge.verify("j" * 64, "POST", path, 1000, body, good, 1000))
        zero = "0" * 64
        self.assertFalse(bridge.verify(zero, "POST", path, 1000, body, bridge.sign(zero, "POST", path, 1000, body), 1000))


class KeepAliveTest(unittest.TestCase):
    def setUp(self):
        from features.brain.keepalive import KeepAlivePolicy
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.policy = KeepAlivePolicy(Path(self.temp.name) / "k.json")

    def test_set_get_clear_and_persist(self):
        from features.brain.keepalive import KeepAlivePolicy
        self.policy.set_many({"qwen2.5-coder:32b-base-q3_K_M": "1h", "cloud:s1/m": "-1"})
        self.assertEqual(self.policy.get("qwen2.5-coder:32b-base-q3_K_M"), "1h")
        self.assertEqual(KeepAlivePolicy(Path(self.temp.name) / "k.json").get("cloud:s1/m"), "-1")
        self.policy.set_many({"cloud:s1/m": None})
        self.assertIsNone(self.policy.get("cloud:s1/m"))

    def test_invalid_values_are_rejected(self):
        for changes in ({"m": "forever"}, {"m": "99999h"}, {"bad ref": "1h"}, {"m": "1 h"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.policy.set_many(changes)

    def test_published_with_the_routes_for_the_core(self):
        from features.brain.keepalive import keep_alive_policy
        service = routing.AssignmentService(Path(self.temp.name) / "brain")
        with patch.object(routing, "keep_alive_policy", self.policy), patch.object(routing.brains, "usable", return_value=True),                 patch.object(service, "role_orders", return_value=ORDERS):
            self.policy.set_many({"m:1": "1h"})
            service.publish()
        self.assertEqual(json.loads(Path(self.temp.name, "brain", "routes.json").read_text())["keep_alive"], {"m:1": "1h"})
        self.assertIsNotNone(keep_alive_policy)


if __name__ == "__main__":
    unittest.main()
