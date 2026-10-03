import json
import os
import shutil
import stat
import time
from typing import Dict, List

from sandbox_broker.backends import Backend, RawResult
from sandbox_broker.config import BrokerConfig
from sandbox_broker.microvm import archive, console, vmconfig
from sandbox_broker.process import run_capped
from sandbox_broker.workspace import Workspace
from server.features.sandbox.domain.errors import SandboxUnavailableError
from server.features.sandbox.domain.spec import ExecutionSpec, Language, NetworkPolicy, ResourceLimits
from server.features.sandbox.domain.strength import Strength

BOOT_ALLOWANCE_SECONDS = 15
KERNEL_FILE = "vmlinux"
ROOTFS_FILE = "rootfs.ext4"
_CONSOLE_FACTOR = 2
_SMOKE_SPEC = ExecutionSpec(
    language=Language.PYTHON,
    source="print('jarvis-microvm-ok')",
    limits=ResourceLimits(memory_mb=64, wall_seconds=30),
)


class MicroVmBackend(Backend):
    name = "firecracker"
    strength = Strength.MICROVM

    def __init__(self, config: BrokerConfig) -> None:
        self._config = config
        self._kernel = os.path.join(config.firecracker_dir, KERNEL_FILE)
        self._rootfs = os.path.join(config.firecracker_dir, ROOTFS_FILE)
        self._ready = False

    def available(self) -> bool:
        return self._ready

    def refresh(self) -> None:
        self._ready = self.prerequisites_met() and self._smoke_test()

    def prerequisites_met(self) -> bool:
        return (
            os.access(self._config.kvm_device, os.R_OK | os.W_OK)
            and os.access(self._config.firecracker_bin, os.X_OK)
            and os.path.isfile(self._kernel)
            and os.path.isfile(self._rootfs)
            and shutil.which("setpriv") is not None
        )

    def run(self, spec: ExecutionSpec, workspace: Workspace) -> RawResult:
        if spec.network is not NetworkPolicy.NONE:
            raise SandboxUnavailableError("the micro-VM backend has no network")
        images = self._write_images(spec, workspace)
        argv = self._launch_argv(spec, workspace, images)
        cap = (spec.limits.output_bytes * 2 + 4096) * _CONSOLE_FACTOR
        result = run_capped(argv, spec.limits.wall_seconds + BOOT_ALLOWANCE_SECONDS, cap, on_timeout=lambda: None)
        report = console.parse(result.stdout, spec.limits.output_bytes)
        self._restore_outputs(images["out"], spec, workspace)
        timed_out = result.timed_out or report.timed_out
        exit_code = report.exit_code if report.complete else (124 if timed_out else 125)
        stderr = report.stderr or (b"" if report.complete else b"micro-VM ended without a report")
        return RawResult(
            exit_code=exit_code,
            stdout=report.stdout,
            stderr=stderr,
            timed_out=timed_out,
            oom_killed=report.oom_killed,
            duration_ms=result.duration_ms,
        )

    def _write_images(self, spec: ExecutionSpec, workspace: Workspace) -> Dict[str, str]:
        inputs = {}
        for entry in os.scandir(workspace.in_dir):
            with open(entry.path, "rb") as handle:
                inputs[entry.name] = handle.read()
        paths = {"in": os.path.join(workspace.path, "in.img"), "out": os.path.join(workspace.path, "out.img"),
                 "config": os.path.join(workspace.path, "vm.json")}
        with open(paths["in"], "wb") as handle:
            handle.write(archive.frame(archive.pack(inputs)))
        with open(paths["out"], "wb") as handle:
            handle.truncate(vmconfig.out_image_size(spec))
        config = vmconfig.build_config(spec, self._kernel, self._rootfs, paths["in"], paths["out"])
        with open(paths["config"], "w", encoding="utf-8") as handle:
            json.dump(config, handle)
        for name in ("in", "out", "config"):
            os.chmod(paths[name], 0o600)
            if hasattr(os, "chown"):
                os.chown(paths[name], self._config.sandbox_uid, self._config.sandbox_uid)
        return paths

    def _launch_argv(self, spec: ExecutionSpec, workspace: Workspace, images: Dict[str, str]) -> List[str]:
        group = str(os.stat(self._config.kvm_device).st_gid)
        uid = str(self._config.sandbox_uid)
        return [
            "setpriv", f"--reuid={uid}", f"--regid={group}", f"--groups={group}", "--no-new-privs",
            self._config.firecracker_bin, "--no-api", "--config-file", images["config"],
        ]

    def _restore_outputs(self, out_image: str, spec: ExecutionSpec, workspace: Workspace) -> None:
        try:
            with open(out_image, "rb") as handle:
                payload = archive.unframe(handle.read(vmconfig.out_image_size(spec)), spec.limits.output_bytes * 2)
            files = archive.unpack(payload, max_files=16, max_bytes=spec.limits.output_bytes)
        except (OSError, archive.ArchiveError):
            return
        for name, content in files.items():
            target = os.path.join(workspace.out_dir, name)
            with open(target, "wb") as handle:
                handle.write(content)
            os.chmod(target, stat.S_IRUSR | stat.S_IWUSR)

    def _smoke_test(self) -> bool:
        started = time.monotonic()
        try:
            with Workspace(self._config.work_dir, _SMOKE_SPEC, self._config.sandbox_uid) as workspace:
                result = self.run(_SMOKE_SPEC, workspace)
        except (OSError, SandboxUnavailableError):
            return False
        return result.exit_code == 0 and b"jarvis-microvm-ok" in result.stdout and time.monotonic() - started < 60
