import json
import logging
import os
import socketserver
import time
from http.server import BaseHTTPRequestHandler
from typing import Callable

from sandbox_broker.engine import Engine
from sandbox_broker.registry import BackendRegistry
from server.features.sandbox import wire
from server.features.sandbox.domain.errors import SandboxUnavailableError, SpecError
from server.features.sandbox.domain.spec import ExecutionSpec

logger = logging.getLogger("jarvis.sandbox_broker")


class BrokerHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    engine: Engine
    registry: BackendRegistry
    key_provider: Callable[[], str]
    max_body: int
    clock: Callable[[], float] = time.time

    def do_GET(self) -> None:
        self._dispatch()

    def do_POST(self) -> None:
        self._dispatch()

    def log_message(self, format: str, *args) -> None:
        logger.debug(format, *args)

    def _dispatch(self) -> None:
        body = self._read_body()
        if body is None:
            return
        if not self._authenticated(body):
            self._reply(401, {"error": "invalid signature"})
            return
        if self.command == "POST" and self.path == wire.EXECUTE_PATH:
            self._execute(body)
        elif self.command == "GET" and self.path == wire.STATUS_PATH:
            self._reply(200, {"backends": self.registry.describe(), "ready": self.registry.any_available()})
        else:
            self._reply(404, {"error": "not found"})

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length < 0 or length > self.max_body:
            self._reply(400, {"error": "invalid body size"})
            return None
        return self.rfile.read(length) if length else b""

    def _authenticated(self, body: bytes) -> bool:
        try:
            timestamp = int(self.headers.get(wire.TIMESTAMP_HEADER, ""))
        except ValueError:
            return False
        signature = self.headers.get(wire.SIGNATURE_HEADER, "")
        return wire.verify(self.key_provider(), self.command, self.path, timestamp, body, signature, self.clock())

    def _execute(self, body: bytes) -> None:
        try:
            spec = ExecutionSpec.from_wire(json.loads(body))
            report = self.engine.execute(spec)
        except (SpecError, json.JSONDecodeError) as exc:
            self._reply(400, {"error": str(exc)})
        except SandboxUnavailableError as exc:
            self._reply(503, {"error": str(exc)})
        except Exception:
            logger.exception("execution failed")
            self._reply(500, {"error": "internal error"})
        else:
            self._reply(200, report.to_wire())

    def _reply(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def bind_handler(engine: Engine, registry: BackendRegistry, key_provider: Callable[[], str], max_body: int, clock=time.time):
    return type(
        "BoundBrokerHandler",
        (BrokerHandler,),
        {"engine": engine, "registry": registry, "key_provider": staticmethod(key_provider), "max_body": max_body, "clock": staticmethod(clock)},
    )


def _unix_server_class():
    class UnixBrokerServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
        daemon_threads = True

        def get_request(self):
            request, _ = super().get_request()
            return request, ("local", 0)

    return UnixBrokerServer


def serve_unix(socket_path: str, handler):
    os.makedirs(os.path.dirname(socket_path), mode=0o750, exist_ok=True)
    if os.path.exists(socket_path):
        os.unlink(socket_path)
    server = _unix_server_class()(socket_path, handler)
    os.chmod(socket_path, 0o660)
    return server
