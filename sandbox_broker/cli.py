import http.client
import json
import socket
import sys
import time

from sandbox_broker.config import BrokerConfig
from sandbox_broker.secret import read_secret
from server.features.sandbox import wire


class _UnixConnection(http.client.HTTPConnection):
    def __init__(self, path: str, timeout: float) -> None:
        super().__init__("localhost", timeout=timeout)
        self._path = path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self._path)


def fetch_status(config: BrokerConfig, timeout: float = 10) -> dict:
    key = read_secret(config.env_file)
    timestamp = int(time.time())
    headers = {
        wire.TIMESTAMP_HEADER: str(timestamp),
        wire.SIGNATURE_HEADER: wire.sign(key, "GET", wire.STATUS_PATH, timestamp, b""),
    }
    connection = _UnixConnection(config.socket_path, timeout)
    try:
        connection.request("GET", wire.STATUS_PATH, headers=headers)
        response = connection.getresponse()
        payload = json.loads(response.read() or b"{}")
        if response.status != 200:
            raise RuntimeError(payload.get("error", f"http {response.status}"))
        return payload
    finally:
        connection.close()


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
