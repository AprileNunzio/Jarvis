import ipaddress
import logging
import select
import socket
import socketserver
import threading
import time
from typing import Callable, Optional, Sequence, Tuple
from urllib.parse import urlsplit

logger = logging.getLogger("jarvis.sandbox_broker.egress")

ALLOWED_PORTS = (80, 443)
HEAD_LIMIT = 16384
CONNECT_TIMEOUT = 10.0
IDLE_TIMEOUT = 30.0
CHUNK = 65536


def host_matches(host: str, patterns: Sequence[str]) -> bool:
    host = host.lower().rstrip(".")
    for pattern in patterns:
        if pattern.startswith("*."):
            if host.endswith(pattern[1:]) and host != pattern[2:]:
                return True
        elif host == pattern:
            return True
    return False


def public_address(host: str, resolver: Callable = socket.getaddrinfo) -> Optional[str]:
    try:
        infos = resolver(host, None, type=socket.SOCK_STREAM)
    except OSError:
        return None
    addresses = [info[4][0] for info in infos]
    if not addresses:
        return None
    for address in addresses:
        try:
            if not ipaddress.ip_address(address.split("%")[0]).is_global:
                return None
        except ValueError:
            return None
    return addresses[0]


def split_target(head: bytes) -> Tuple[str, str, int, bytes]:
    line, _, rest = head.partition(b"\r\n")
    parts = line.decode("latin-1").split()
    if len(parts) != 3:
        raise ValueError("malformed request line")
    method, target, version = parts
    if method.upper() == "CONNECT":
        host, _, port = target.rpartition(":")
        return "CONNECT", host, int(port), b""
    url = urlsplit(target)
    if url.scheme != "http" or not url.hostname:
        raise ValueError("only absolute http URLs are proxied")
    path = (url.path or "/") + (f"?{url.query}" if url.query else "")
    forwarded = f"{method} {path} {version}\r\n".encode("latin-1") + _strip_hop_headers(rest)
    return method.upper(), url.hostname, url.port or 80, forwarded


def _strip_hop_headers(raw: bytes) -> bytes:
    kept = [h for h in raw.split(b"\r\n") if h and not h.lower().startswith((b"proxy-", b"connection:"))]
    return b"\r\n".join(kept + [b"Connection: close", b"", b""])


class _Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        proxy: "EgressProxy" = self.server.proxy
        client: socket.socket = self.request
        client.settimeout(CONNECT_TIMEOUT)
        try:
            head, leftover = self._read_head(client)
            method, host, port, forwarded = split_target(head)
        except (ValueError, OSError):
            self._reply(client, 400, "Bad Request")
            return
        if port not in ALLOWED_PORTS or not host_matches(host, proxy.allowed):
            proxy.denied.append(host)
            self._reply(client, 403, "Forbidden")
            return
        address = public_address(host, proxy.resolver)
        if address is None:
            proxy.denied.append(host)
            self._reply(client, 403, "Forbidden")
            return
        try:
            upstream = proxy.connect((address, port), CONNECT_TIMEOUT)
        except OSError:
            self._reply(client, 502, "Bad Gateway")
            return
        with upstream:
            if method == "CONNECT":
                client.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
            else:
                upstream.sendall(forwarded + leftover)
            proxy.carried += self._pipe(client, upstream, proxy)

    @staticmethod
    def _read_head(client: socket.socket) -> Tuple[bytes, bytes]:
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = client.recv(4096)
            if not chunk or len(data) > HEAD_LIMIT:
                raise ValueError("incomplete request")
            data += chunk
        head, _, leftover = data.partition(b"\r\n\r\n")
        return head + b"\r\n\r\n", leftover

    @staticmethod
    def _reply(client: socket.socket, status: int, text: str) -> None:
        try:
            client.sendall(f"HTTP/1.1 {status} {text}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".encode())
        except OSError:
            return

    @staticmethod
    def _pipe(a: socket.socket, b: socket.socket, proxy: "EgressProxy") -> int:
        carried, sockets = 0, [a, b]
        while time.monotonic() < proxy.deadline and carried < proxy.max_bytes:
            readable, _, _ = select.select(sockets, [], [], IDLE_TIMEOUT)
            if not readable:
                break
            for source in readable:
                data = source.recv(CHUNK)
                if not data:
                    return carried
                (b if source is a else a).sendall(data)
                carried += len(data)
        return carried


class EgressProxy:
    def __init__(
        self,
        bind_host: str,
        allowed: Sequence[str],
        lifetime_seconds: float,
        max_bytes: int = 16 * 1024 * 1024,
        port_range: Tuple[int, int] = (0, 0),
        resolver: Callable = socket.getaddrinfo,
        connect: Callable = socket.create_connection,
    ) -> None:
        self.allowed = tuple(h.lower() for h in allowed)
        self.deadline = time.monotonic() + lifetime_seconds
        self.max_bytes = max_bytes
        self.resolver, self.connect = resolver, connect
        self.denied: list = []
        self.carried = 0
        self._server = self._bind(bind_host, port_range)
        self._server.proxy = self
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True, name="egress-proxy")

    @staticmethod
    def _bind(host: str, port_range: Tuple[int, int]) -> "_ThreadingServer":
        low, high = port_range
        for port in range(low, high + 1):
            try:
                return _ThreadingServer((host, port), _Handler)
            except OSError:
                continue
        raise OSError(f"no free proxy port in {low}-{high}")

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    def start(self) -> "EgressProxy":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def __enter__(self) -> "EgressProxy":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()


class _ThreadingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True
    proxy: EgressProxy
