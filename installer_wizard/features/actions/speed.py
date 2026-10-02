import asyncio
import time

import httpx

SPEED_URL = "https://speed.cloudflare.com"


async def speed_action(text: str) -> tuple[str, dict]:
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "Jarvis-OS"}) as client:
        pings = []
        for _ in range(5):
            t = time.perf_counter()
            await client.get(f"{SPEED_URL}/__down", params={"bytes": 0})
            pings.append((time.perf_counter() - t) * 1000)

        async def download(size: int) -> float:
            t, got = time.perf_counter(), 0
            async with client.stream("GET", f"{SPEED_URL}/__down", params={"bytes": size}) as r:
                async for chunk in r.aiter_bytes():
                    got += len(chunk)
            return got * 8 / (time.perf_counter() - t) / 1e6

        await download(1_000_000)
        downs = await asyncio.gather(*(download(25_000_000) for _ in range(4)))
        down = sum(downs)
        payload = b"0" * 10_000_000

        async def upload() -> float:
            t = time.perf_counter()
            await client.post(f"{SPEED_URL}/__up", content=payload)
            return len(payload) * 8 / (time.perf_counter() - t) / 1e6

        up = sum(await asyncio.gather(*(upload() for _ in range(3))))
    ping = min(pings)
    jitter = sum(abs(a - b) for a, b in zip(pings, pings[1:])) / max(1, len(pings) - 1)
    f = lambda v: f"{v:.1f}".replace(".", ",")
    speech = (
        f"La connessione va a {f(down)} megabit al secondo in download e {f(up)} in upload, "
        f"con una latenza di {ping:.0f} millisecondi."
    )
    return speech, {
        "mode": "focus",
        "title": "Velocità della connessione",
        "subtitle": "Test reale verso Cloudflare",
        "panels": [
            {
                "type": "stats",
                "title": "Risultato",
                "items": [
                    {"label": "Download", "value": f"{f(down)} Mbit/s", "percent": min(100, down / 10)},
                    {"label": "Upload", "value": f"{f(up)} Mbit/s", "percent": min(100, up / 10)},
                    {"label": "Latenza", "value": f"{ping:.0f} ms (jitter {jitter:.0f})", "percent": min(100, ping)},
                ],
            }
        ],
    }
