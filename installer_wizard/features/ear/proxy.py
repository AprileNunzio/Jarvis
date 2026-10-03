import asyncio
import logging
from typing import Any

import websockets
from fastapi import WebSocket, WebSocketDisconnect

import auth

logger = logging.getLogger("jarvis.ear.proxy")
UPSTREAM = "ws://127.0.0.1:8093"
MAX_MESSAGE = 2 ** 22
DENIED = 4401


def allowed(socket: WebSocket) -> bool:
    peer = socket.client.host if socket.client else ""
    return peer in ("127.0.0.1", "::1", "localhost") or bool(auth.verify(socket.cookies.get(auth.SESSION_COOKIE)))


async def _up(client: Any, upstream: Any) -> None:
    while True:
        message = await client.receive()
        if message["type"] == "websocket.disconnect":
            return
        if message.get("bytes") is not None:
            await upstream.send(message["bytes"])
        elif message.get("text") is not None:
            await upstream.send(message["text"])


async def _down(client: Any, upstream: Any) -> None:
    async for message in upstream:
        if isinstance(message, bytes):
            await client.send_bytes(message)
        else:
            await client.send_text(message)


async def pump(client: Any, upstream: Any) -> None:
    tasks = [asyncio.create_task(_up(client, upstream)), asyncio.create_task(_down(client, upstream))]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def proxy(socket: WebSocket) -> None:
    if not allowed(socket):
        await socket.close(code=DENIED)
        return
    await socket.accept()
    try:
        async with websockets.connect(UPSTREAM, max_size=MAX_MESSAGE) as upstream:
            await pump(socket, upstream)
    except (OSError, websockets.WebSocketException, WebSocketDisconnect, RuntimeError) as exc:
        logger.info("ear proxy closed: %s", exc)
    try:
        await socket.close()
    except RuntimeError:
        return
