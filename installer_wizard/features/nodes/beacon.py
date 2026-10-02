import asyncio
import json
import logging
import socket
import time

from config import PUBLIC_PORT

log = logging.getLogger("jarvis.nodes")

DISCOVER_PORT = 50505
ANNOUNCE_PORT = 50506
EVERY = 15
MAX_SEEN = 128


def _payload() -> bytes:
    return json.dumps({"jarvis": "master", "v": 1, "name": socket.gethostname()[:60], "port": PUBLIC_PORT}).encode()


class _Protocol(asyncio.DatagramProtocol):

    def __init__(self, beacon: "Beacon") -> None:
        self.beacon = beacon
        self.transport = None

    def connection_made(self, transport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr) -> None:
        if len(data) > 1024:
            return
        try:
            msg = json.loads(data)
        except ValueError:
            return
        if not isinstance(msg, dict) or msg.get("jarvis") not in ("discover", "node"):
            return
        self.beacon.note(addr[0], msg)
        if msg.get("jarvis") == "discover":
            self.transport.sendto(_payload(), addr)


class Beacon:

    def __init__(self) -> None:
        self.seen: dict[str, dict] = {}

    def note(self, ip: str, msg: dict) -> None:
        node_id = str(msg.get("id") or "")[:48]
        if not node_id:
            return
        self.seen[node_id] = {"id": node_id, "ip": ip, "paired": bool(msg.get("paired")), "at": time.time(),
                              "version": str(msg.get("version") or "")[:20]}
        if len(self.seen) > MAX_SEEN:
            oldest = min(self.seen, key=lambda k: self.seen[k]["at"])
            self.seen.pop(oldest, None)

    def found(self, within: float = 300) -> list[dict]:
        now = time.time()
        return [s for s in self.seen.values() if now - s["at"] < within]

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        try:
            transport, _ = await loop.create_datagram_endpoint(lambda: _Protocol(self), local_addr=("0.0.0.0", DISCOVER_PORT),
                                                               allow_broadcast=True)
        except OSError as exc:
            log.warning("Annuncio dei nodi non disponibile: %s", exc)
            return
        try:
            while True:
                try:
                    transport.sendto(_payload(), ("255.255.255.255", ANNOUNCE_PORT))
                except OSError as exc:
                    log.debug("Annuncio non inviato: %s", exc)
                await asyncio.sleep(EVERY)
        finally:
            transport.close()


beacon = Beacon()
