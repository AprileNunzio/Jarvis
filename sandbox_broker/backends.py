import subprocess
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple

from sandbox_broker.config import BrokerConfig
from sandbox_broker.docker_cmd import build_run_argv
from sandbox_broker.egress import EgressProxy
from sandbox_broker.egress_network import EgressNetwork
from sandbox_broker.process import run_capped
from sandbox_broker.workspace import Workspace
from server.features.sandbox.domain.errors import SandboxUnavailableError
from server.features.sandbox.domain.spec import ExecutionSpec, Language, NetworkPolicy, ResourceLimits
from server.features.sandbox.domain.strength import Strength

_OOM_EXIT = 137
_SMOKE_SPEC = ExecutionSpec(
    language=Language.PYTHON,
    source="print('jarvis-sandbox-ok')",
    limits=ResourceLimits(memory_mb=64, wall_seconds=60),
)


@dataclass(frozen=True)
class RawResult:
    exit_code: int
    stdout: bytes
    stderr: bytes
    timed_out: bool
    oom_killed: bool
    duration_ms: int
    egress_denied: Tuple[str, ...] = ()


class Backend(ABC):
    name: str
    strength: Strength

    def supports_egress(self) -> bool:
        return False

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def refresh(self) -> None: ...

    @abstractmethod
    def run(self, spec: ExecutionSpec, workspace: Workspace) -> RawResult: ...


class DockerBackend(Backend):
    def __init__(
        self, config: BrokerConfig, name: str, strength: Strength, runtime: Optional[str], network: Optional[EgressNetwork] = None
    ) -> None:
        self.name = name
        self._network = network
        self.strength = strength
        self._config = config
        self._runtime = runtime
        self._ready = False

    def available(self) -> bool:
        return self._ready

    def refresh(self) -> None:
        self._ready = self._runtime_registered() and self._smoke_test()

    def supports_egress(self) -> bool:
        return self._network is not None and self._network.ready

    def run(self, spec: ExecutionSpec, workspace: Workspace) -> RawResult:
        if spec.network is NetworkPolicy.ALLOWLIST:
            if not self.supports_egress():
                raise SandboxUnavailableError("the egress network is not available")
            with EgressProxy(
                self._network.proxy_host, spec.egress_hosts, spec.limits.wall_seconds + 5,
                port_range=self._config.egress_ports,
            ) as proxy:
                return self._execute(spec, workspace, f"http://{self._network.proxy_host}:{proxy.port}", proxy)
        return self._execute(spec, workspace, "", None)

    def _execute(self, spec: ExecutionSpec, workspace: Workspace, proxy_url: str, proxy: Optional[EgressProxy]) -> RawResult:
        container = f"{self._config.container_prefix}{uuid.uuid4().hex[:16]}"
        argv = build_run_argv(
            self._config.docker_bin, container, self._config.image, spec,
            workspace.in_dir, workspace.out_dir, self._config.sandbox_uid, self._runtime,
            self._config.egress_network, proxy_url,
        )
        result = run_capped(
            argv, spec.limits.wall_seconds, spec.limits.output_bytes,
            on_timeout=lambda: self._kill(container),
        )
        return RawResult(
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            timed_out=result.timed_out,
            oom_killed=not result.timed_out and result.exit_code == _OOM_EXIT,
            duration_ms=result.duration_ms,
            egress_denied=tuple(dict.fromkeys(proxy.denied)) if proxy else (),
        )

    def _kill(self, container: str) -> None:
        subprocess.run([self._config.docker_bin, "kill", container], capture_output=True, timeout=15, check=False)

    def _runtime_registered(self) -> bool:
        if not self._runtime:
            return True
        try:
            listing = subprocess.run(
                [self._config.docker_bin, "info", "--format", "{{json .Runtimes}}"],
                capture_output=True, timeout=20, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return f'"{self._runtime}"'.encode() in listing.stdout

    def _smoke_test(self) -> bool:
        try:
            with Workspace(self._config.work_dir, _SMOKE_SPEC, self._config.sandbox_uid) as workspace:
                result = self.run(_SMOKE_SPEC, workspace)
        except (OSError, subprocess.SubprocessError):
            return False
        return result.exit_code == 0 and b"jarvis-sandbox-ok" in result.stdout
