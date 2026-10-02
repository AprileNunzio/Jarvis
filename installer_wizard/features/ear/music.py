import asyncio
import io
import json
import logging
import os
import time
import urllib.error
import urllib.request
import wave
from collections import deque

import numpy as np

log = logging.getLogger("jarvis.ear")

RATE = 16000
FRAME = 480
MUSIC_URL = f"http://127.0.0.1:{os.environ.get('JARVIS_ADMIN_PORT', '8080')}/api/internal/music"
WINDOW = 10.0
LOUD_RATIO = 0.88
STATE = {"next_at": time.time() + 60, "busy": False}


def _post(audio: np.ndarray) -> dict:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())
    req = urllib.request.Request(MUSIC_URL, data=buf.getvalue(), method="POST",
                                 headers={"Content-Type": "audio/wav", "X-Jarvis-Request": "1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"{}")


async def _probe(audio: np.ndarray) -> None:
    try:
        result = await asyncio.to_thread(_post, audio)
        wait = float(result.get("next_in", 120))
        if result.get("found"):
            log.info("Musica riconosciuta: %s", result.get("title"))
    except (OSError, urllib.error.URLError, ValueError) as exc:
        log.debug("Riconoscimento musicale non disponibile: %s", exc)
        wait = 600
    STATE.update(busy=False, next_at=time.time() + max(20.0, wait))


class MusicTap:

    def __init__(self) -> None:
        self.ring = np.zeros(RATE * 12, dtype=np.float32)
        self.pos = 0
        self.filled = 0
        self.loud = deque(maxlen=int(WINDOW * RATE / FRAME))
        self.loud_count = 0

    def feed(self, frame: np.ndarray, rms: float, noise: float, idle: bool, now: float) -> None:
        ring, n, pos = self.ring, len(frame), self.pos
        if pos + n <= len(ring):
            ring[pos:pos + n] = frame
        else:
            k = len(ring) - pos
            ring[pos:], ring[:n - k] = frame[:k], frame[k:]
        self.pos = (pos + n) % len(ring)
        self.filled = min(len(ring), self.filled + n)
        loud = rms > max(noise * 2.0, 0.006) and idle
        if len(self.loud) == self.loud.maxlen:
            self.loud_count -= self.loud[0]
        self.loud.append(loud)
        self.loud_count += loud
        if (STATE["busy"] or now < STATE["next_at"] or not idle or len(self.loud) < self.loud.maxlen
                or self.filled < len(ring) or self.loud_count < LOUD_RATIO * len(self.loud)):
            return
        audio = np.concatenate([ring[self.pos:], ring[:self.pos]])[-int(RATE * WINDOW):]
        STATE.update(busy=True, next_at=now + 60)
        asyncio.create_task(_probe(audio))
