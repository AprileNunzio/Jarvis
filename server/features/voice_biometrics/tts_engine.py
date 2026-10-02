import logging
import os
import shutil
import subprocess
import wave
from io import BytesIO

from server.features.voice_biometrics.audio_contracts import TTSRequest

logger = logging.getLogger("jarvis.tts")

MODELS_DIR = os.environ.get("JARVIS_TTS_MODELS_DIR", "/app/data/models/tts")
SAMPLE_RATE = 22050


class PiperTTSEngine:
    def __init__(self, models_dir: str = MODELS_DIR, executable_path: str = "piper"):
        self.models_dir = models_dir
        self.executable_path = executable_path

    def _model_path(self, voice_profile: str) -> str:
        return os.path.join(self.models_dir, f"{voice_profile}.onnx")

    def is_available(self, voice_profile: str = "it_IT-paola-medium") -> bool:
        return shutil.which(self.executable_path) is not None and os.path.exists(self._model_path(voice_profile))

    def generate_speech_raw(self, text: str, voice_profile: str, speed: float = 1.0) -> bytes:
        model_path = self._model_path(voice_profile)
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"TTS model not found: {model_path}")

        command = [
            self.executable_path,
            "--model", model_path,
            "--length_scale", str(round(1.0 / max(speed, 0.1), 3)),
            "--output_raw",
        ]
        process = subprocess.run(command, input=text.encode("utf-8"), capture_output=True, timeout=60)
        if process.returncode != 0:
            raise RuntimeError(f"Piper failed: {process.stderr.decode(errors='ignore')[:200]}")
        return process.stdout

    def synthesize_speech_wav(self, request: TTSRequest) -> bytes:
        try:
            raw = self.generate_speech_raw(request.text, request.voice_profile, request.speed)
        except (FileNotFoundError, RuntimeError, subprocess.TimeoutExpired) as exc:
            logger.warning("TTS unavailable: %s", exc)
            return b""

        buffer = BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(raw)
        return buffer.getvalue()


tts_engine = PiperTTSEngine()
