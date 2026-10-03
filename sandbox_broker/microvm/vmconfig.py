import base64
import json
import math
from typing import Any, Dict

from server.features.sandbox.domain.spec import ExecutionSpec

GUEST_OVERHEAD_MB = 96
BOOT_ARGS = "console=ttyS0 reboot=k panic=1 pci=off nomodules 8250.nr_uarts=1 random.trust_cpu=on i8042.noaux ro init=/sbin/jarvis-init"
FRAME_HEADROOM = 64 * 1024


def guest_spec(spec: ExecutionSpec) -> str:
    payload = {
        "language": spec.language.value,
        "wall": spec.limits.wall_seconds,
        "out": spec.limits.output_bytes,
        "pids": spec.limits.pids,
    }
    return base64.b64encode(json.dumps(payload, separators=(",", ":")).encode("ascii")).decode("ascii")


def memory_mib(spec: ExecutionSpec) -> int:
    return spec.limits.memory_mb + GUEST_OVERHEAD_MB + math.ceil(spec.limits.output_bytes / (1024 * 1024)) + 16


def out_image_size(spec: ExecutionSpec) -> int:
    return spec.limits.output_bytes + FRAME_HEADROOM + 64 * 1024


def build_config(spec: ExecutionSpec, kernel: str, rootfs: str, in_image: str, out_image: str) -> Dict[str, Any]:
    return {
        "boot-source": {"kernel_image_path": kernel, "boot_args": f"{BOOT_ARGS} jarvis.spec={guest_spec(spec)}"},
        "drives": [
            {"drive_id": "rootfs", "path_on_host": rootfs, "is_root_device": True, "is_read_only": True},
            {"drive_id": "input", "path_on_host": in_image, "is_root_device": False, "is_read_only": True},
            {"drive_id": "output", "path_on_host": out_image, "is_root_device": False, "is_read_only": False},
        ],
        "machine-config": {"vcpu_count": max(1, math.ceil(spec.limits.cpus)), "mem_size_mib": memory_mib(spec), "smt": False},
    }
