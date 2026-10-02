import logging
import os
import time
from pathlib import Path

import numpy as np

log = logging.getLogger("jarvis.ear")

MODELS = Path(os.environ.get("JARVIS_WAKEWORD_MODELS", "/opt/jarvis-ear/wakeword"))
MODEL_NAME = "hey_jarvis_v0.1"
CHUNK = 1280
THRESHOLD = float(os.environ.get("JARVIS_WAKEWORD_THRESHOLD", "0.5"))
COOLDOWN = 2.0


class WakeWord:

    def __init__(self) -> None:
        self.model = None
        self.pending = np.zeros(0, dtype=np.int16)
        self.last_hit = 0.0
        self.score = 0.0
        files = [MODELS / f"{MODEL_NAME}.onnx", MODELS / "melspectrogram.onnx", MODELS / "embedding_model.onnx"]
        if os.environ.get("JARVIS_WAKEWORD", "1") == "0" or not all(f.exists() for f in files):
            log.info("Rilevatore istantaneo non disponibile: uso solo il riconoscimento del parlato")
            return
        try:
            from openwakeword.model import Model
            self.model = self._build(Model, files)
            log.info("Rilevatore istantaneo «Ehi Jarvis» attivo (soglia %.2f)", THRESHOLD)
        except Exception as exc:
            log.warning("Rilevatore istantaneo non avviato: %s", exc)
            self.model = None

    @staticmethod
    def _build(model_cls, files: list):
        word, mel, emb = (str(f) for f in files)
        variants = (
            {"wakeword_models": [word], "inference_framework": "onnx", "melspec_model_path": mel, "embedding_model_path": emb},
            {"wakeword_model_paths": [word], "inference_framework": "onnx", "melspec_model_path": mel, "embedding_model_path": emb},
            {"wakeword_model_paths": [word], "melspec_model_path": mel, "embedding_model_path": emb},
            {"wakeword_model_paths": [word], "melspec_onnx_model_path": mel, "embedding_onnx_model_path": emb},
            {"wakeword_models": [word], "inference_framework": "onnx"},
            {"wakeword_model_paths": [word]},
        )
        errors = []
        for kwargs in variants:
            try:
                model = model_cls(**kwargs)
                log.info("openWakeWord avviato con i parametri: %s", ", ".join(kwargs))
                return model
            except TypeError as exc:
                errors.append(str(exc))
        raise RuntimeError("nessuna combinazione di parametri accettata: " + " | ".join(errors[-2:]))

    @property
    def ready(self) -> bool:
        return self.model is not None

    def feed(self, frame: np.ndarray) -> bool:
        if self.model is None:
            return False
        pcm = (np.clip(frame, -1, 1) * 32767).astype(np.int16)
        self.pending = np.concatenate([self.pending, pcm])
        hit = False
        while len(self.pending) >= CHUNK:
            chunk, self.pending = self.pending[:CHUNK], self.pending[CHUNK:]
            try:
                self.score = float(self.model.predict(chunk).get(MODEL_NAME, 0.0))
            except Exception as exc:
                log.warning("Rilevatore istantaneo disattivato dopo un errore: %s", exc)
                self.model = None
                return False
            now = time.time()
            if self.score >= THRESHOLD and now - self.last_hit > COOLDOWN:
                self.last_hit = now
                hit = True
        return hit

    def reset(self) -> None:
        if self.model is not None:
            self.model.reset()
        self.pending = np.zeros(0, dtype=np.int16)
