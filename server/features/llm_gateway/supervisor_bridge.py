import hashlib
import hmac
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx

from server.config.env import settings

logger = logging.getLogger("jarvis.llm_gateway.bridge")

COMPLETE_PATH = "/api/internal/brain/complete"
TRACE_PATH = "/api/internal/brain/trace"
CLOUD_PREFIX = "cloud:"
MUTE_SECONDS = 30.0


def is_remote_ref(ref: str) -> bool:
    return ref.startswith(CLOUD_PREFIX)


def sign(key: str, method: str, path: str, timestamp: int, body: bytes) -> str:
    message = b"\n".join([method.upper().encode(), path.encode(), str(timestamp).encode(), hashlib.sha256(body).digest()])
    return hmac.new(key.encode("utf-8"), message, hashlib.sha256).hexdigest()


class BridgeError(RuntimeError):
    pass


class SupervisorBridge:
    def __init__(self, base_url: str = "", key_provider=lambda: settings.JARVIS_SECRET_KEY) -> None:
        self._base = base_url
        self._key = key_provider
        self._muted_until = 0.0

    @property
    def base_url(self) -> str:
        return self._base or settings.JARVIS_SUPERVISOR_URL

    def _headers(self, path: str, body: bytes) -> Dict[str, str]:
        stamp = int(time.time())
        return {"X-Jarvis-Timestamp": str(stamp), "X-Jarvis-Signature": sign(self._key(), "POST", path, stamp, body),
                "Content-Type": "application/json"}

    async def _post(self, path: str, payload: Dict[str, Any], timeout: float) -> httpx.Response:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=3)) as client:
            return await client.post(f"{self.base_url}{path}", content=body, headers=self._headers(path, body))

    async def complete(self, ref: str, messages: List[Dict[str, str]], system: Optional[str], max_tokens: int,
                       temperature: float, timeout: float = 180.0) -> Dict[str, Any]:
        try:
            response = await self._post(COMPLETE_PATH, {"ref": ref, "messages": messages, "system": system or "",
                                                        "max_tokens": max_tokens, "temperature": temperature}, timeout)
        except httpx.HTTPError as exc:
            raise BridgeError(f"supervisor unreachable: {type(exc).__name__}") from exc
        if response.status_code != 200:
            raise BridgeError(f"{response.status_code}: {response.text[:200]}")
        return response.json()

    async def report(self, op: str, call: str, **fields: Any) -> None:
        if time.monotonic() < self._muted_until:
            return
        try:
            await self._post(TRACE_PATH, {"op": op, "call": call, **fields}, 3.0)
        except httpx.HTTPError as exc:
            self._muted_until = time.monotonic() + MUTE_SECONDS
            logger.debug("trace report dropped: %s", exc)


class CallTrace:
    def __init__(self, bridge: SupervisorBridge, component: str, note: str, chain: List[str]) -> None:
        self._bridge = bridge
        self._call = uuid.uuid4().hex[:24]
        self._ready = False
        self._component, self._note, self._chain = component, note, chain

    async def _send(self, op: str, **fields: Any) -> None:
        if not self._ready:
            self._ready = True
            await self._bridge.report("begin", self._call, component=self._component, note=self._note, chain=self._chain)
        await self._bridge.report(op, self._call, **fields)

    async def attempt(self, ref: str) -> None:
        await self._send("attempt", ref=ref)

    async def failed(self, ref: str, reason: str) -> None:
        await self._send("failed", ref=ref, reason=reason)

    async def done(self, ref: str, ms: float, snippet: str) -> None:
        await self._send("done", ref=ref, ms=ms, snippet=snippet[:200])

    async def abort(self, reason: str) -> None:
        await self._send("abort", reason=reason)


bridge = SupervisorBridge()
