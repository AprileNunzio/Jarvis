import threading
from typing import Callable, List, Optional, Sequence

from sandbox_broker.backends import Backend
from server.features.sandbox.domain.errors import SandboxUnavailableError
from server.features.sandbox.domain.strength import Strength


class BackendRegistry:
    def __init__(self, backends: Sequence[Backend]) -> None:
        self._backends: List[Backend] = sorted(backends, key=lambda b: b.strength, reverse=True)
        self._stop = threading.Event()

    def select(self, minimum: Strength, needs_egress: bool = False) -> Backend:
        for backend in self._backends:
            if backend.strength >= minimum and backend.available() and (backend.supports_egress() or not needs_egress):
                return backend
        raise SandboxUnavailableError(f"no isolation backend available with strength >= {int(minimum)}")

    def refresh(self) -> None:
        for backend in self._backends:
            backend.refresh()

    def describe(self) -> List[dict]:
        return [{"name": b.name, "strength": int(b.strength), "available": b.available()} for b in self._backends]

    def any_available(self) -> bool:
        return any(b.available() for b in self._backends)

    def keep_fresh(self, interval_seconds: int, on_cycle: Optional[Callable[[], None]] = None) -> threading.Thread:
        def loop() -> None:
            while not self._stop.wait(interval_seconds):
                self.refresh()
                if on_cycle:
                    on_cycle()

        thread = threading.Thread(target=loop, name="backend-probe", daemon=True)
        thread.start()
        return thread

    def stop(self) -> None:
        self._stop.set()
