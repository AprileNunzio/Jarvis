import json
import time
from typing import Callable, Optional

import httpx

from server.features.sandbox import wire
from server.features.sandbox.domain.errors import SandboxRejectedError, SandboxUnavailableError, SpecError
from server.features.sandbox.domain.report import ExecutionReport
from server.features.sandbox.domain.spec import ExecutionSpec

_TRANSPORT_MARGIN_SECONDS = 20


class BrokerClient:
    def __init__(
        self,
        socket_path: str,
        key_provider: Callable[[], str],
        transport: Optional[httpx.AsyncBaseTransport] = None,
        clock: Callable[[], float] = time.time,
        base_url: str = "http://sandbox-broker",
    ) -> None:
        self._transport = transport or httpx.AsyncHTTPTransport(uds=socket_path)
        self._base_url = base_url
        self._key = key_provider
        self._clock = clock

    async def execute(self, spec: ExecutionSpec) -> ExecutionReport:
        body = json.dumps(spec.to_wire(), separators=(",", ":")).encode("utf-8")
        response = await self._post(wire.EXECUTE_PATH, body, spec.limits.wall_seconds + _TRANSPORT_MARGIN_SECONDS)
        if response.status_code == 200:
            return ExecutionReport.from_wire(response.json())
        detail = self._detail(response)
        if response.status_code == 400:
            raise SpecError(detail)
        if response.status_code in (401, 403):
            raise SandboxRejectedError(detail)
        raise SandboxUnavailableError(detail)

    async def status(self) -> dict:
        response = await self._post(wire.STATUS_PATH, b"", 10, method="GET")
        if response.status_code != 200:
            raise SandboxUnavailableError(self._detail(response))
        return response.json()

    async def _post(self, path: str, body: bytes, timeout: float, method: str = "POST") -> httpx.Response:
        timestamp = int(self._clock())
        headers = {
            wire.TIMESTAMP_HEADER: str(timestamp),
            wire.SIGNATURE_HEADER: wire.sign(self._key(), method, path, timestamp, body),
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(transport=self._transport, base_url=self._base_url, timeout=timeout) as client:
                return await client.request(method, path, content=body, headers=headers)
        except httpx.HTTPError as exc:
            raise SandboxUnavailableError(f"sandbox broker unreachable: {exc.__class__.__name__}") from exc

    @staticmethod
    def _detail(response: httpx.Response) -> str:
        try:
            return str(response.json().get("error", response.text))
        except ValueError:
            return response.text[:200] or f"http {response.status_code}"
