import logging
import signal
import threading

from sandbox_broker.backends import DockerBackend
from sandbox_broker.config import BrokerConfig
from sandbox_broker.egress_network import EgressNetwork
from sandbox_broker.microvm.backend import MicroVmBackend
from sandbox_broker.engine import Engine
from sandbox_broker.housekeeping import remove_stale_workspaces, remove_stray_containers
from sandbox_broker.registry import BackendRegistry
from sandbox_broker.secret import secret_provider
from sandbox_broker.server import bind_handler, serve_unix
from server.features.sandbox.domain.strength import Strength

logger = logging.getLogger("jarvis.sandbox_broker")


def build_registry(config: BrokerConfig, network: EgressNetwork) -> BackendRegistry:
    return BackendRegistry([
        MicroVmBackend(config),
        DockerBackend(config, "gvisor", Strength.USERSPACE_KERNEL, "runsc", network),
        DockerBackend(config, "container", Strength.CONTAINER, None, network),
    ])


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    config = BrokerConfig.from_env()
    remove_stray_containers(config)
    remove_stale_workspaces(config)
    network = EgressNetwork(config)
    logger.info("egress network ready: %s", network.ensure())
    registry = build_registry(config, network)
    registry.refresh()
    logger.info("backends: %s", registry.describe())
    registry.keep_fresh(config.probe_interval_seconds, lambda: (network.ensure(), remove_stray_containers(config), remove_stale_workspaces(config)))
    engine = Engine(config, registry, config.sandbox_uid)
    handler = bind_handler(engine, registry, secret_provider(config.env_file), config.max_body_bytes)
    server = serve_unix(config.socket_path, handler)
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=server.shutdown, daemon=True).start())
    logger.info("listening on %s", config.socket_path)
    try:
        server.serve_forever()
    finally:
        registry.stop()
        server.server_close()


if __name__ == "__main__":
    main()
