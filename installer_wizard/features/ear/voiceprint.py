import json
import logging
import os
import re
import threading
import time
from pathlib import Path

import numpy as np

log = logging.getLogger("jarvis.ear")

MODEL = Path(os.environ.get("JARVIS_VOICEPRINT_MODEL", "/opt/jarvis-ear/voiceprint/speaker.onnx"))
STORE = Path(os.environ.get("JARVIS_VOICEPRINTS", "/var/lib/jarvis/voiceprints"))
RATE = 16000
MIN_SECONDS = 1.0
MATCH = float(os.environ.get("JARVIS_VOICEPRINT_MATCH", "0.62"))
MARGIN = 0.06
MAX_SAMPLES = 40
ENROLLED_AT = 5
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")


class Voiceprints:

    def __init__(self) -> None:
        self.extractor = None
        self.lock = threading.Lock()
        self.prints: dict[str, np.ndarray] = {}
        self.stamp = 0.0
        if os.environ.get("JARVIS_VOICEPRINT", "1") == "0" or not MODEL.exists():
            log.info("Impronta vocale non disponibile su questo sistema")
            return
        try:
            import sherpa_onnx
            config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(MODEL), num_threads=2)
            self.extractor = sherpa_onnx.SpeakerEmbeddingExtractor(config)
            STORE.mkdir(parents=True, exist_ok=True)
            os.chmod(STORE, 0o700)
            self._load()
            log.info("Impronta vocale attiva: %d persone", len(self.prints))
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            log.warning("Impronta vocale non avviata: %s", exc)
            self.extractor = None

    @property
    def ready(self) -> bool:
        return self.extractor is not None

    def _load(self) -> None:
        prints = {}
        for f in STORE.glob("*.npy"):
            try:
                samples = np.load(f)
                prints[f.stem] = _unit(samples.mean(axis=0))
            except (OSError, ValueError):
                continue
        with self.lock:
            self.prints = prints

    def embed(self, audio: np.ndarray) -> np.ndarray | None:
        if not self.ready or len(audio) < RATE * MIN_SECONDS:
            return None
        stream = self.extractor.create_stream()
        stream.accept_waveform(RATE, audio.astype(np.float32))
        stream.input_finished()
        if not self.extractor.is_ready(stream):
            return None
        return _unit(np.array(self.extractor.compute(stream), dtype=np.float32))

    def _refresh(self) -> None:
        try:
            stamp = STORE.stat().st_mtime
        except OSError:
            return
        if stamp != self.stamp:
            self.stamp = stamp
            self._load()

    def identify(self, emb: np.ndarray | None) -> tuple[str | None, float]:
        if emb is None:
            return None, 0.0
        self._refresh()
        with self.lock:
            scores = sorted(((float(p @ emb), slug) for slug, p in self.prints.items()), reverse=True)
        if not scores:
            return None, 0.0
        best, slug = scores[0]
        second = scores[1][0] if len(scores) > 1 else 0.0
        return (slug, best) if best >= MATCH and best - second >= MARGIN else (None, best)

    def add(self, slug: str, emb: np.ndarray, source: str) -> int:
        if not _SLUG.match(slug) or emb is None:
            return 0
        path = STORE / f"{slug}.npy"
        try:
            samples = list(np.load(path)) if path.exists() else []
        except (OSError, ValueError):
            samples = []
        samples = (samples + [emb])[-MAX_SAMPLES:]
        np.save(path, np.array(samples, dtype=np.float32))
        meta = {"samples": len(samples), "updated": time.time(), "source": source, "enrolled": len(samples) >= ENROLLED_AT}
        (STORE / f"{slug}.json").write_text(json.dumps(meta), encoding="utf-8")
        self._load()
        return len(samples)

    def count(self, slug: str) -> int:
        try:
            return json.loads((STORE / f"{slug}.json").read_text(encoding="utf-8")).get("samples", 0)
        except (OSError, ValueError):
            return 0

    def forget(self, slug: str) -> None:
        if not _SLUG.match(slug):
            return
        for ext in ("npy", "json"):
            (STORE / f"{slug}.{ext}").unlink(missing_ok=True)
        self._load()


def _unit(v: np.ndarray) -> np.ndarray:
    return v / max(float(np.linalg.norm(v)), 1e-9)
