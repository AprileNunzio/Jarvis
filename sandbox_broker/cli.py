import json
import sys

from sandbox_broker.config import BrokerConfig
from sandbox_broker.unix_client import signed_request
from server.features.sandbox import wire


def fetch_status(config: BrokerConfig, timeout: float = 10) -> dict:
    status, payload = signed_request(config, "GET", wire.STATUS_PATH, timeout=timeout)
    if status != 200:
        raise RuntimeError(payload.get("error", f"http {status}"))
    return payload


def main(argv: list) -> int:
    if len(argv) != 2 or argv[1] != "status":
        print("usage: python -m sandbox_broker.cli status", file=sys.stderr)
        return 2
    try:
        status = fetch_status(BrokerConfig.from_env())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"unavailable: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(status))
    return 0 if status.get("ready") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
