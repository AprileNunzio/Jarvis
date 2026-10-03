import http.client
import json
import socket
import time
from typing import Any, Dict, Optional, Tuple

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


def signed_request(
    config: BrokerConfig,
    method: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: float = 10,
) -> Tuple[int, Dict[str, Any]]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8") if payload is not None else b""
    timestamp = int(time.time())
    headers = {
        wire.TIMESTAMP_HEADER: str(timestamp),
        wire.SIGNATURE_HEADER: wire.sign(read_secret(config.env_file), method, path, timestamp, body),
        "Content-Type": "application/json",
    }
    connection = _UnixConnection(config.socket_path, timeout)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read() or b"{}")
    finally:
        connection.close()
