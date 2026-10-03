import unittest

from server.features.sandbox import wire
from server.features.sandbox.domain.errors import SpecError
from server.features.sandbox.domain.report import Artifact, ExecutionReport
from server.features.sandbox.domain.spec import ExecutionSpec, Language, ResourceLimits
from server.features.sandbox.domain.strength import Strength


def make_spec(**overrides):
    values = {"language": Language.PYTHON, "source": "print(1)"}
    values.update(overrides)
    return ExecutionSpec(**values)


class SpecValidationTest(unittest.TestCase):
    def test_valid_spec_passes(self):
        make_spec(inputs={"data.csv": b"a,b"}).validate()

    def test_rejects_empty_source(self):
        with self.assertRaises(SpecError):
            make_spec(source="   ").validate()

    def test_rejects_oversized_source(self):
        with self.assertRaises(SpecError):
            make_spec(source="x" * (256 * 1024 + 1)).validate()

    def test_rejects_path_traversal_in_input_names(self):
        for name in ("../etc/passwd", "a/b", ".hidden", "", "x" * 65):
            with self.subTest(name=name), self.assertRaises(SpecError):
                make_spec(inputs={name: b"x"}).validate()

    def test_rejects_too_many_inputs(self):
        with self.assertRaises(SpecError):
            make_spec(inputs={f"f{i}": b"x" for i in range(17)}).validate()

    def test_rejects_limits_out_of_range(self):
        for limits in (
            ResourceLimits(memory_mb=8),
            ResourceLimits(memory_mb=4096),
            ResourceLimits(cpus=8),
            ResourceLimits(pids=1),
            ResourceLimits(wall_seconds=0),
            ResourceLimits(wall_seconds=3600),
            ResourceLimits(output_bytes=10),
        ):
            with self.subTest(limits=limits), self.assertRaises(SpecError):
                make_spec(limits=limits).validate()


class SpecWireTest(unittest.TestCase):
    def test_round_trip_preserves_everything(self):
        spec = make_spec(
            language=Language.BASH,
            inputs={"in.bin": bytes(range(256))},
            limits=ResourceLimits(memory_mb=256, wall_seconds=10),
            min_strength=Strength.USERSPACE_KERNEL,
        )
        self.assertEqual(ExecutionSpec.from_wire(spec.to_wire()), spec)

    def test_malformed_payloads_raise_spec_error(self):
        for payload in (
            {},
            {"language": "ruby", "source": "x"},
            {"language": "python", "source": "x", "inputs": {"a": "***"}},
            {"language": "python", "source": "x", "limits": {"unknown": 1}},
            {"language": "python", "source": "x", "min_strength": 9},
            {"language": "python", "source": "x", "network": "all"},
        ):
            with self.subTest(payload=payload), self.assertRaises(SpecError):
                ExecutionSpec.from_wire(payload)


class ReportWireTest(unittest.TestCase):
    def test_round_trip(self):
        report = ExecutionReport(0, "out", "err", False, False, "gvisor", 2, 12, (Artifact("a.txt", b"\x00\xff"),), True)
        self.assertEqual(ExecutionReport.from_wire(report.to_wire()), report)

    def test_succeeded_requires_clean_exit(self):
        base = dict(stdout="", stderr="", backend="c", strength=1)
        self.assertTrue(ExecutionReport(exit_code=0, timed_out=False, oom_killed=False, **base).succeeded)
        self.assertFalse(ExecutionReport(exit_code=1, timed_out=False, oom_killed=False, **base).succeeded)
        self.assertFalse(ExecutionReport(exit_code=0, timed_out=True, oom_killed=False, **base).succeeded)
        self.assertFalse(ExecutionReport(exit_code=0, timed_out=False, oom_killed=True, **base).succeeded)


class SignatureTest(unittest.TestCase):
    KEY = "k" * 64

    def sign(self, **overrides):
        args = {"method": "POST", "path": wire.EXECUTE_PATH, "timestamp": 1000, "body": b"{}"}
        args.update(overrides)
        return wire.sign(self.KEY, args["method"], args["path"], args["timestamp"], args["body"])

    def verify(self, signature, now=1000, **overrides):
        args = {"method": "POST", "path": wire.EXECUTE_PATH, "timestamp": 1000, "body": b"{}", "key": self.KEY}
        args.update(overrides)
        return wire.verify(args["key"], args["method"], args["path"], args["timestamp"], args["body"], signature, now)

    def test_valid_signature_verifies(self):
        self.assertTrue(self.verify(self.sign()))

    def test_tampering_with_any_component_fails(self):
        signature = self.sign()
        self.assertFalse(self.verify(signature, body=b"{ }"))
        self.assertFalse(self.verify(signature, method="GET"))
        self.assertFalse(self.verify(signature, path=wire.STATUS_PATH))
        self.assertFalse(self.verify(signature, timestamp=1001))
        self.assertFalse(self.verify(signature, key="z" * 64))

    def test_stale_timestamp_is_rejected(self):
        self.assertFalse(self.verify(self.sign(), now=1000 + wire.MAX_SKEW_SECONDS + 1))
        self.assertTrue(self.verify(self.sign(), now=1000 + wire.MAX_SKEW_SECONDS))

    def test_default_zero_key_is_never_accepted(self):
        zero = "0" * 64
        signature = wire.sign(zero, "POST", wire.EXECUTE_PATH, 1000, b"{}")
        self.assertFalse(wire.verify(zero, "POST", wire.EXECUTE_PATH, 1000, b"{}", signature, 1000))
        self.assertFalse(wire.verify("", "POST", wire.EXECUTE_PATH, 1000, b"{}", signature, 1000))


if __name__ == "__main__":
    unittest.main()
