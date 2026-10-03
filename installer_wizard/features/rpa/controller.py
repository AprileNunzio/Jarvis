import base64
from dataclasses import dataclass, field
from typing import Protocol

from features.rpa.broker import RpaOffline, RpaTimeout
from features.rpa.steps import Step
from features.vision.ui_anchor import Screen, UiElement, image_size

MIN_EFFECT = 0.002
MIN_CONTRAST = 3.0
MIN_DISTANCE = 12


class Locator(Protocol):
    async def locate(self, png: bytes, query: str, screen: Screen) -> list[UiElement]: ...


class Transport(Protocol):
    async def submit(self, node_id: str, instruction: dict, timeout: float = 45.0) -> dict: ...


@dataclass
class StepTrace:
    number: int
    do: str
    ok: bool = False
    attempts: list[dict] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict:
        return {"step": self.number, "do": self.do, "ok": self.ok, "attempts": self.attempts, "message": self.message}


@dataclass
class RunTrace:
    ok: bool
    steps: list[StepTrace]
    message: str

    def to_dict(self) -> dict:
        return {"ok": self.ok, "message": self.message, "steps": [s.to_dict() for s in self.steps]}


class RpaController:
    def __init__(self, transport: Transport, locator: Locator, max_attempts: int = 3, store_frame=None) -> None:
        self._transport = transport
        self._locator = locator
        self._max_attempts = max_attempts
        self._store_frame = store_frame

    async def run(self, node_id: str, steps: list[Step]) -> RunTrace:
        traces: list[StepTrace] = []
        for number, step in enumerate(steps, start=1):
            trace = StepTrace(number, step.do)
            traces.append(trace)
            try:
                await self._perform(node_id, step, trace)
            except (RpaOffline, RpaTimeout) as exc:
                trace.message = str(exc)
            if not trace.ok:
                return RunTrace(False, traces, f"Passo {number} non riuscito: {trace.message}")
        return RunTrace(True, traces, f"{len(steps)} passi eseguiti e verificati")

    async def _perform(self, node_id: str, step: Step, trace: StepTrace) -> None:
        if step.pointer:
            await self._pointer(node_id, step, trace)
            return
        result = await self._send(node_id, self._instruction(step))
        trace.attempts.append(self._summary(result))
        trace.ok, trace.message = self._judge(result, step.expect_change)

    async def _pointer(self, node_id: str, step: Step, trace: StepTrace) -> None:
        failed: list[tuple[int, int]] = []
        for attempt in range(1, self._max_attempts + 1):
            frame = await self._send(node_id, {"action": "capture"})
            if not frame.get("ok") or not frame.get("frame"):
                trace.message = frame.get("error", "cattura dello schermo non riuscita")
                return
            png = base64.b64decode(frame["frame"])
            if self._store_frame:
                self._store_frame(node_id, png)
            width, height = image_size(png)
            candidates = await self._locator.locate(png, step.target, Screen(width, height, tuple(failed)))
            element = self._pick(candidates, failed)
            if element is None:
                trace.attempts.append({"attempt": attempt, "found": False})
                trace.message = f"elemento «{step.target}» non trovato sullo schermo"
                continue
            cx, cy = element.center
            result = await self._send(node_id, {"action": step.do, "x": cx, "y": cy, "region": element.box, "min_contrast": MIN_CONTRAST})
            summary = {"attempt": attempt, "element": element.to_dict(), **self._summary(result)}
            trace.attempts.append(summary)
            if result.get("ok") and result["data"].get("acted") is False:
                failed.append((cx, cy))
                trace.message = f"l'area individuata in ({cx}, {cy}) è uniforme: probabilmente non è un elemento"
                continue
            ok, message = self._judge(result, step.expect_change)
            if ok:
                trace.ok, trace.message = True, message
                return
            failed.append((cx, cy))
            trace.message = message

    @staticmethod
    def _pick(candidates: list[UiElement], failed: list[tuple[int, int]]) -> UiElement | None:
        for element in candidates:
            cx, cy = element.center
            if all(abs(cx - fx) > MIN_DISTANCE or abs(cy - fy) > MIN_DISTANCE for fx, fy in failed):
                return element
        return None

    @staticmethod
    def _instruction(step: Step) -> dict:
        if step.do == "type":
            return {"action": "type", "text": step.text}
        if step.do == "key":
            return {"action": "key", "keys": list(step.keys)}
        if step.do == "scroll":
            return {"action": "scroll", "amount": step.amount}
        return {"action": "wait", "seconds": step.seconds}

    async def _send(self, node_id: str, instruction: dict) -> dict:
        return await self._transport.submit(node_id, instruction)

    @staticmethod
    def _summary(result: dict) -> dict:
        if not result.get("ok"):
            return {"ok": False, "error": result.get("error", "errore sconosciuto")}
        data = result.get("data", {})
        return {"ok": True, "changed_ratio": data.get("changed_ratio"), "region_ratio": data.get("region_ratio"),
                "settled": data.get("settled"), "acted": data.get("acted", True)}

    @staticmethod
    def _judge(result: dict, expect_change: bool) -> tuple[bool, str]:
        if not result.get("ok"):
            return False, result.get("error", "errore del nodo")
        data = result.get("data", {})
        effect = max(data.get("changed_ratio") or 0.0, data.get("region_ratio") or 0.0)
        if not expect_change:
            return True, "eseguito"
        if effect >= MIN_EFFECT:
            return True, f"verificato: {effect * 100:.1f}% dello schermo è cambiato"
        return False, "nessuna variazione visibile dello schermo dopo l'azione"
