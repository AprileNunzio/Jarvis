import subprocess

from sandbox_broker.config import BrokerConfig


class EgressNetwork:
    def __init__(self, config: BrokerConfig) -> None:
        self._config = config
        self.ready = False

    @property
    def proxy_host(self) -> str:
        return self._config.egress_gateway

    def ensure(self) -> bool:
        c = self._config
        try:
            exists = subprocess.run([c.docker_bin, "network", "inspect", c.egress_network], capture_output=True, timeout=20, check=False)
            if exists.returncode != 0:
                created = subprocess.run(
                    [c.docker_bin, "network", "create", "--internal", "--driver", "bridge",
                     "--subnet", c.egress_subnet, "--gateway", c.egress_gateway,
                     "--opt", f"com.docker.network.bridge.name={c.egress_bridge}", c.egress_network],
                    capture_output=True, timeout=30, check=False,
                )
                if created.returncode != 0:
                    self.ready = False
                    return False
            self.ready = True
        except (OSError, subprocess.SubprocessError):
            self.ready = False
        return self.ready
