import json
import sys
from typing import Any, Dict, List

from sandbox_broker.config import BrokerConfig
from sandbox_broker.unix_client import signed_request
from server.features.sandbox import wire
from server.features.sandbox.domain.report import ExecutionReport
from server.features.sandbox.domain.spec import ExecutionSpec, Language, ResourceLimits

PROBE_SOURCE = """
import json, os, socket
result = {"uid": os.getuid()}
try:
    socket.create_connection(("1.1.1.1", 53), timeout=3).close()
    result["network"] = "open"
except OSError:
    result["network"] = "blocked"
try:
    open("/probe", "w").close()
    result["rootfs"] = "writable"
except OSError:
    result["rootfs"] = "readonly"
result["docker_socket"] = os.path.exists("/var/run/docker.sock")
result["host_config"] = os.path.exists("/etc/jarvis")
with open("/out/proof.txt", "w") as handle:
    handle.write("artifact")
print(json.dumps(result))
"""

EXPECTED = {"network": "blocked", "rootfs": "readonly", "docker_socket": False, "host_config": False}


def evaluate(report: ExecutionReport) -> Dict[str, Any]:
    problems: List[str] = []
    if not report.succeeded:
        problems.append(f"exit {report.exit_code}: {report.stderr[-200:]}")
    observed: Dict[str, Any] = {}
    try:
        observed = json.loads(report.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        problems.append("probe output unreadable")
    for key, expected in EXPECTED.items():
        if observed.get(key) != expected:
            problems.append(f"{key}={observed.get(key)!r} (expected {expected!r})")
    if observed.get("uid") in (0, None):
        problems.append("process runs as root")
    if {a.name: a.content for a in report.artifacts} != {"proof.txt": b"artifact"}:
        problems.append("artifact not returned intact")
    return {"ok": not problems, "backend": report.backend, "strength": report.strength, "problems": problems}


def run_selfcheck(config: BrokerConfig) -> Dict[str, Any]:
    spec = ExecutionSpec(language=Language.PYTHON, source=PROBE_SOURCE, limits=ResourceLimits(wall_seconds=30))
    status, payload = signed_request(config, "POST", wire.EXECUTE_PATH, spec.to_wire(), timeout=60)
    if status != 200:
        return {"ok": False, "backend": "", "strength": 0, "problems": [payload.get("error", f"http {status}")]}
    return evaluate(ExecutionReport.from_wire(payload))


def main() -> int:
    try:
        outcome = run_selfcheck(BrokerConfig.from_env())
    except (OSError, ValueError) as exc:
        outcome = {"ok": False, "backend": "", "strength": 0, "problems": [f"broker unreachable: {exc}"]}
    print(json.dumps(outcome))
    return 0 if outcome["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
