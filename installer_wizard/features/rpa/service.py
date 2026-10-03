import asyncio

from config import env_get
from state import store

from features.brain.llm import BrainUnavailable
from features.rpa.broker import broker
from features.rpa.controller import RpaController, RunTrace
from features.rpa.locator import VisionLocator
from features.rpa.steps import parse_steps

NEED_VISION = ("Per trovare gli elementi sullo schermo mi serve un cervello che vede le immagini: aggiungi nel Cervello "
               "un servizio cloud come GPT-4o, Claude o Gemini, oppure un modello locale come llava.")


def allowed_nodes() -> set[str]:
    return {n.strip() for n in env_get("JARVIS_RPA_NODES", "").split(",") if n.strip()}


class RpaService:
    def __init__(self) -> None:
        self._controller = RpaController(broker, VisionLocator(), store_frame=broker.last_frame.__setitem__)
        self._locks: dict[str, asyncio.Lock] = {}

    def permitted(self, node_id: str) -> bool:
        return env_get("JARVIS_RPA", "0") == "1" and node_id in allowed_nodes()

    async def run(self, node_id: str, raw_steps, user: str = "agente") -> RunTrace:
        if not self.permitted(node_id):
            raise PermissionError("Il controllo di questo nodo non è abilitato nelle impostazioni di «Controllo del computer»")
        steps = parse_steps(raw_steps)
        async with self._locks.setdefault(node_id, asyncio.Lock()):
            store.event("INFO", f"Controllo del nodo {node_id} avviato da {user}: {len(steps)} passi", "rpa")
            try:
                trace = await self._controller.run(node_id, steps)
            except BrainUnavailable:
                raise RuntimeError(NEED_VISION) from None
            store.event("INFO" if trace.ok else "WARN", f"Controllo del nodo {node_id}: {trace.message}", "rpa")
            return trace


rpa = RpaService()
