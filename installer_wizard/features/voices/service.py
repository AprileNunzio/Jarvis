import io
import json
import logging
import os
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
from kokoro_onnx import Kokoro

logging.basicConfig(level=logging.INFO, format="%(asctime)s [jarvis.voice] %(levelname)s: %(message)s")
log = logging.getLogger("jarvis.voice")

BASE = os.environ.get("JARVIS_KOKORO_DIR", "/opt/jarvis-voice/kokoro")
PORT = int(os.environ.get("JARVIS_VOICE_PORT", "8092"))
DEFAULT_VOICE = "im_nicola"
LANGS = {"a": "en-us", "b": "en-gb", "e": "es", "f": "fr-fr", "h": "hi", "i": "it", "j": "ja", "p": "pt-br", "z": "cmn"}

started = time.time()
kokoro = Kokoro(f"{BASE}/kokoro-v1.0.onnx", f"{BASE}/voices-v1.0.bin")
VOICES = sorted(kokoro.get_voices())
lock = threading.Lock()
log.info("Kokoro caricato in %.1fs — %d voci", time.time() - started, len(VOICES))


def synthesize(text: str, voice: str, speed: float) -> bytes:
    lang = LANGS.get(voice[:1], "en-us")
    with lock:
        samples, rate = kokoro.create(text, voice=voice, speed=speed, lang=lang)
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    return buffer.getvalue()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, json.dumps({"status": "ok", "engine": "kokoro", "voices": VOICES,
                                        "uptime": int(time.time() - started)}).encode())
        else:
            self._send(404, b'{"error":"not found"}')

    def do_POST(self):
        if self.path != "/tts":
            return self._send(404, b'{"error":"not found"}')
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            text = str(body.get("text", "")).strip()[:1200]
            voice = body.get("voice") or DEFAULT_VOICE
            speed = max(0.6, min(1.6, float(body.get("speed", 1.0))))
            if not text:
                return self._send(400, b'{"error":"testo vuoto"}')
            if voice not in VOICES:
                return self._send(400, json.dumps({"error": f"voce sconosciuta: {voice}"}).encode())
            t = time.time()
            wav = synthesize(text, voice, speed)
            log.info("%d caratteri sintetizzati in %.2fs", len(text), time.time() - t)
            self._send(200, wav, "audio/wav")
        except Exception as exc:
            log.exception("Sintesi non riuscita")
            self._send(500, json.dumps({"error": str(exc)}).encode())

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
