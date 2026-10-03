import asyncio
import time
import uuid


class RpaTimeout(Exception):
    pass


class RpaOffline(Exception):
    pass


ONLINE_WINDOW = 75.0


class RpaBroker:
    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue] = {}
        self._pending: dict[str, tuple[str, asyncio.Future]] = {}
        self._seen: dict[str, dict] = {}
        self.last_frame: dict[str, bytes] = {}

    def note_poll(self, node_id: str, info: dict) -> None:
        screen = info.get("screen")
        valid = isinstance(screen, list) and len(screen) == 2 and all(isinstance(v, int) and 0 < v < 20000 for v in screen)
        self._seen[node_id] = {"at": time.time(), "screen": screen if valid else None, "version": str(info.get("version", ""))[:20],
                               "sha": str(info.get("sha", ""))[:64]}

    def online(self, node_id: str) -> bool:
        seen = self._seen.get(node_id)
        return bool(seen) and time.time() - seen["at"] < ONLINE_WINDOW

    def info(self, node_id: str) -> dict | None:
        return self._seen.get(node_id)

    def known(self) -> list[str]:
        return [n for n in self._seen if self.online(n)]

    async def submit(self, node_id: str, instruction: dict, timeout: float = 45.0) -> dict:
        if not self.online(node_id):
            raise RpaOffline("Il demone di controllo del nodo non è raggiungibile")
        ident = uuid.uuid4().hex
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[ident] = (node_id, future)
        await self._queue(node_id).put({**instruction, "id": ident})
        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            raise RpaTimeout("il nodo non ha risposto in tempo") from None
        finally:
            self._pending.pop(ident, None)

    async def poll(self, node_id: str, wait: float = 20.0) -> dict | None:
        try:
            return await asyncio.wait_for(self._queue(node_id).get(), wait)
        except asyncio.TimeoutError:
            return None

    def complete(self, node_id: str, result: dict) -> bool:
        entry = self._pending.get(str(result.get("id", "")))
        if not entry or entry[0] != node_id or entry[1].done():
            return False
        entry[1].set_result(result)
        return True

    def _queue(self, node_id: str) -> asyncio.Queue:
        return self._queues.setdefault(node_id, asyncio.Queue(maxsize=8))


broker = RpaBroker()
