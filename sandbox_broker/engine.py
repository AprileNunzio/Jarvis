import threading
from typing import Optional

from sandbox_broker.collector import collect
from sandbox_broker.config import BrokerConfig
from sandbox_broker.registry import BackendRegistry
from sandbox_broker.workspace import Workspace
from server.features.sandbox.domain.errors import SandboxUnavailableError
from server.features.sandbox.domain.report import ExecutionReport
from server.features.sandbox.domain.spec import ExecutionSpec


class Engine:
    def __init__(self, config: BrokerConfig, registry: BackendRegistry, owner_uid: Optional[int]) -> None:
        self._config = config
        self._registry = registry
        self._uid = owner_uid
        self._slots = threading.BoundedSemaphore(config.max_concurrent)

    def execute(self, spec: ExecutionSpec) -> ExecutionReport:
        spec.validate()
        backend = self._registry.select(spec.min_strength)
        if not self._slots.acquire(timeout=self._config.queue_wait_seconds):
            raise SandboxUnavailableError("sandbox is busy")
        try:
            with Workspace(self._config.work_dir, spec, self._uid) as workspace:
                raw = backend.run(spec, workspace)
                artifacts, truncated = collect(workspace.out_dir, spec.limits)
        finally:
            self._slots.release()
        limit = spec.limits.output_bytes
        return ExecutionReport(
            exit_code=raw.exit_code,
            stdout=raw.stdout[:limit].decode("utf-8", "replace"),
            stderr=raw.stderr[:limit].decode("utf-8", "replace"),
            timed_out=raw.timed_out,
            oom_killed=raw.oom_killed,
            backend=backend.name,
            strength=int(backend.strength),
            duration_ms=raw.duration_ms,
            artifacts=artifacts,
            artifacts_truncated=truncated,
            egress_denied=raw.egress_denied,
        )
