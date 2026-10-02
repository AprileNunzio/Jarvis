import httpx
from fastapi import HTTPException
from fastapi.responses import Response, StreamingResponse

from access import NO_CACHE

VISION_URL = "http://127.0.0.1:8091"


async def vision_proxy(path: str, method: str = "GET", json_body=None, timeout: float = 10) -> Response:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.request(method, f"{VISION_URL}{path}", json=json_body)
    except httpx.HTTPError:
        raise HTTPException(503, "Servizio di visione non disponibile")
    return Response(r.content, status_code=r.status_code, media_type=r.headers.get("content-type"),
                    headers=NO_CACHE)


async def vision_stream(path: str = "/stream.mjpg") -> StreamingResponse:
    async def relay():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("GET", f"{VISION_URL}{path}") as r:
                    async for chunk in r.aiter_bytes():
                        yield chunk
        except httpx.HTTPError:
            return
    return StreamingResponse(relay(), media_type="multipart/x-mixed-replace; boundary=frame", headers=NO_CACHE)


async def snapshot() -> bytes | None:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{VISION_URL}/snapshot.jpg")
        return r.content if r.status_code == 200 else None
    except httpx.HTTPError:
        return None


async def frame() -> bytes | None:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{VISION_URL}/frame.jpg")
        return r.content if r.status_code == 200 else None
    except httpx.HTTPError:
        return None
