import base64
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from sandbox_broker.backends import Backend
from sandbox_broker.config import BrokerConfig
from sandbox_broker.microvm import archive, console, vmconfig
from sandbox_broker.microvm import backend as microvm
from sandbox_broker.process import ProcessResult
from sandbox_broker.registry import BackendRegistry
from sandbox_broker.workspace import Workspace
from server.features.sandbox.domain.errors import SandboxUnavailableError
from server.features.sandbox.domain.spec import ExecutionSpec, Language, NetworkPolicy, ResourceLimits
from server.features.sandbox.domain.strength import Strength


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def line(key, value):
    raw = value if isinstance(value, bytes) else str(value).encode()
    return b"@@JARVIS@@ " + key.encode() + b" " + base64.b64encode(raw) + b"\n"


class ArchiveTest(unittest.TestCase):
    def test_round_trip_through_a_frame(self):
        files = {"a.txt": b"one", "b.bin": bytes(range(256))}
        image = archive.frame(archive.pack(files)) + b"\0" * 4096
        self.assertEqual(len(archive.frame(b"x")) % 512, 0)
        self.assertEqual(archive.unpack(archive.unframe(image, 1 << 20), 16, 1 << 20), files)

    def test_hostile_archives_cannot_escape_or_exhaust(self):
        with self.assertRaises(archive.ArchiveError):
            archive.pack({"../evil": b"x"})
        with self.assertRaises(archive.ArchiveError):
            archive.unframe((10 ** 9).to_bytes(8, "big") + b"abc", 1 << 20)
        with self.assertRaises(archive.ArchiveError):
            archive.unframe(b"short", 10)
        with self.assertRaises(archive.ArchiveError):
            archive.unpack(b"not a tar at all" * 100, 16, 1 << 20)

    def test_member_filters(self):
        import io
        import tarfile
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as handle:
            for name, kind in (("ok.txt", tarfile.REGTYPE), ("link", tarfile.SYMTYPE), ("../up", tarfile.REGTYPE),
                               ("dir", tarfile.DIRTYPE), ("big.bin", tarfile.REGTYPE)):
                info = tarfile.TarInfo(name)
                info.type = kind
                data = b"x" * 2000 if name == "big.bin" else b"hi"
                info.size = len(data) if kind == tarfile.REGTYPE else 0
                info.linkname = "/etc/passwd" if kind == tarfile.SYMTYPE else ""
                handle.addfile(info, io.BytesIO(data) if kind == tarfile.REGTYPE else None)
        self.assertEqual(archive.unpack(buffer.getvalue(), 16, 1000), {"ok.txt": b"hi"})


class ConsoleTest(unittest.TestCase):
    def test_parses_a_complete_report_between_kernel_noise(self):
        raw = b"[    0.1] booting\n" + line("stdout", b"hello\n") + line("stderr", b"warn") + line("exit", 3) + b"[ 1.0] reboot\n"
        report = console.parse(raw, 1024)
        self.assertEqual((report.stdout, report.stderr, report.exit_code, report.complete), (b"hello\n", b"warn", 3, True))

    def test_flags_oom_timeout_and_incomplete_runs(self):
        self.assertTrue(console.parse(b"Out of memory: Killed process 5\n", 10).oom_killed)
        self.assertTrue(console.parse(line("stdout", b"") + line("timeout", 1) + line("exit", -9), 10).timed_out)
        self.assertTrue(console.parse(line("exit", 137), 10).oom_killed)
        self.assertFalse(console.parse(line("timeout", 1) + line("exit", 137), 10).oom_killed)
        self.assertFalse(console.parse(b"garbage\n@@JARVIS@@ stdout !!!\n", 10).complete)

    def test_tail_keeps_the_last_kernel_lines_and_the_vmm_error_only(self):
        raw = b"".join(b"[ %d] line" % i + bytes([10]) for i in range(10)) + line("stdout", b"secret") + b"Kernel panic - not syncing" + bytes([10])
        text = console.tail(raw, b" firecracker:  cannot open /dev/kvm ")
        self.assertIn("Kernel panic", text)
        self.assertIn("cannot open /dev/kvm", text)
        self.assertNotIn("secret", text)
        self.assertNotIn("[ 0]", text)
        trace = console.tail(bytes([10]).join([b"[    0.5] Run /sbin/jarvis-init", b"Traceback (most recent call last):", b"OSError: mount /proc", b"[    0.6] Kernel panic - not syncing: Attempted to kill init", b"[    0.6] RDX: 0000"]), b"")
        self.assertIn("OSError: mount /proc", trace)
        self.assertNotIn("RDX", trace)

    def test_a_guest_cannot_exceed_the_output_cap(self):
        self.assertEqual(len(console.parse(line("stdout", b"x" * 5000), 100).stdout), 100)


class ConfigTest(unittest.TestCase):
    def spec(self, **limits):
        return ExecutionSpec(Language.PYTHON, "print(1)", ResourceLimits(**limits))

    def test_no_network_device_and_read_only_system_drives(self):
        config = vmconfig.build_config(self.spec(), "/k", "/r", "/i", "/o")
        self.assertNotIn("network-interfaces", config)
        drives = {d["drive_id"]: d for d in config["drives"]}
        self.assertTrue(drives["rootfs"]["is_read_only"] and drives["rootfs"]["is_root_device"])
        self.assertTrue(drives["input"]["is_read_only"])
        self.assertFalse(drives["output"]["is_read_only"])

    def test_resources_follow_the_limits(self):
        config = vmconfig.build_config(self.spec(memory_mb=256, cpus=1.5), "/k", "/r", "/i", "/o")
        self.assertEqual(config["machine-config"]["vcpu_count"], 2)
        self.assertGreater(config["machine-config"]["mem_size_mib"], 256)
        self.assertFalse(config["machine-config"]["smt"])

    def test_guest_spec_round_trips(self):
        encoded = vmconfig.guest_spec(self.spec(wall_seconds=12, pids=40))
        decoded = json.loads(base64.b64decode(encoded))
        self.assertEqual((decoded["language"], decoded["wall"], decoded["pids"]), ("python", 12, 40))
        self.assertIn("jarvis.spec=", vmconfig.build_config(self.spec(), "/k", "/r", "/i", "/o")["boot-source"]["boot_args"])


class BackendTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = BrokerConfig(work_dir=os.path.join(self.temp.name, "work"), firecracker_dir=self.temp.name,
                                   firecracker_bin=os.path.join(self.temp.name, "firecracker"),
                                   kvm_device=os.path.join(self.temp.name, "kvm"))
        self.backend = microvm.MicroVmBackend(self.config)
        self.spec = ExecutionSpec(Language.PYTHON, "print('hi')", inputs={"input.json": b"{}"})

    def run_with(self, console_output, out_files=None, timed_out=False):
        captured = {}

        def fake(argv, wall, cap, on_timeout):
            captured["argv"], captured["wall"] = argv, wall
            config = read_json(argv[argv.index("--config-file") + 1])
            drives = {d["drive_id"]: d["path_on_host"] for d in config["drives"]}
            captured["input"] = archive.unpack(archive.unframe(read_bytes(drives["input"]), 1 << 20), 16, 1 << 20)
            if out_files is not None:
                with open(drives["output"], "r+b") as handle:
                    handle.write(archive.frame(archive.pack(out_files)))
            return ProcessResult(0, console_output, b"", timed_out, 1200)

        open(self.config.kvm_device, "w").close()
        with patch.object(microvm, "run_capped", fake), patch.object(microvm.os, "stat") as stat_mock:
            stat_mock.return_value.st_gid = 7
            with Workspace(self.config.work_dir, self.spec, None) as workspace:
                result = self.backend.run(self.spec, workspace)
                restored = sorted(os.listdir(workspace.out_dir))
        return result, captured, restored

    def test_successful_run_returns_streams_and_artifacts(self):
        result, captured, restored = self.run_with(line("stdout", b"hi\n") + line("exit", 0), {"proof.txt": b"artifact"})
        self.assertEqual((result.exit_code, result.stdout, result.timed_out), (0, b"hi\n", False))
        self.assertEqual(restored, ["proof.txt"])
        self.assertEqual(set(captured["input"]), {"main.py", "input.json"})

    def test_process_is_launched_unprivileged_without_new_privileges_and_api(self):
        _, captured, _ = self.run_with(line("exit", 0))
        argv = captured["argv"]
        self.assertEqual(argv[0], "setpriv")
        for flag in ("--reuid=65534", "--regid=7", "--groups=7", "--no-new-privs", "--no-api"):
            self.assertIn(flag, argv)
        self.assertGreater(captured["wall"], self.spec.limits.wall_seconds)

    def test_missing_report_is_a_failure_not_a_success(self):
        result, _, _ = self.run_with(b"kernel panic\n")
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(b"without a report", result.stderr)

    def test_host_timeout_is_reported(self):
        result, _, _ = self.run_with(b"", timed_out=True)
        self.assertEqual((result.timed_out, result.exit_code), (True, 124))

    def test_hostile_output_image_is_ignored(self):
        def fake(argv, wall, cap, on_timeout):
            config = read_json(argv[argv.index("--config-file") + 1])
            out = [d["path_on_host"] for d in config["drives"] if d["drive_id"] == "output"][0]
            with open(out, "r+b") as handle:
                handle.write((10 ** 12).to_bytes(8, "big") + b"junk")
            return ProcessResult(0, line("exit", 0), b"", False, 5)

        open(self.config.kvm_device, "w").close()
        with patch.object(microvm, "run_capped", fake), patch.object(microvm.os, "stat") as stat_mock:
            stat_mock.return_value.st_gid = 7
            with Workspace(self.config.work_dir, self.spec, None) as workspace:
                self.backend.run(self.spec, workspace)
                self.assertEqual(os.listdir(workspace.out_dir), [])

    def test_network_requests_are_refused(self):
        spec = ExecutionSpec(Language.PYTHON, "x=1", network=NetworkPolicy.ALLOWLIST, egress_hosts=("api.example.com",))
        with Workspace(self.config.work_dir, spec, None) as workspace, self.assertRaises(SandboxUnavailableError):
            self.backend.run(spec, workspace)
        self.assertFalse(self.backend.supports_egress())

    def test_unavailable_without_kvm_binary_or_images(self):
        self.assertFalse(self.backend.prerequisites_met())
        self.backend.refresh()
        self.assertFalse(self.backend.available())
        self.assertEqual((self.backend.name, self.backend.strength), ("firecracker", Strength.MICROVM))
        for missing in ("kvm", "firecracker", "kernel", "rootfs"):
            self.assertIn(missing, self.backend.note)


class StubBackend(Backend):
    def __init__(self, name, strength, egress=False):
        self.name, self.strength, self._egress = name, strength, egress

    def available(self):
        return True

    def refresh(self):
        pass

    def supports_egress(self):
        return self._egress

    def run(self, spec, workspace):
        raise NotImplementedError


class RegistryTest(unittest.TestCase):
    def test_strongest_wins_but_egress_needs_a_capable_backend(self):
        registry = BackendRegistry([StubBackend("fc", Strength.MICROVM), StubBackend("gv", Strength.USERSPACE_KERNEL, True),
                                    StubBackend("c", Strength.CONTAINER, True)])
        self.assertEqual(registry.select(Strength.CONTAINER).name, "fc")
        self.assertEqual(registry.select(Strength.CONTAINER, needs_egress=True).name, "gv")
        with self.assertRaises(SandboxUnavailableError):
            registry.select(Strength.MICROVM, needs_egress=True)


if __name__ == "__main__":
    unittest.main()
