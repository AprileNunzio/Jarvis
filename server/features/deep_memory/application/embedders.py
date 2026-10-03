import hashlib
import logging
import re
from typing import List, Optional

from server.features.deep_memory.application.ports import Embedder

logger = logging.getLogger("jarvis.deep_memory.embedders")
_WORD = re.compile(r"\w{2,}", re.UNICODE)


class HashingEmbedder:
    def __init__(self, dimensions: int = 256) -> None:
        self._dimensions = dimensions

    async def embed(self, text: str) -> List[float]:
        tokens = _WORD.findall(text.lower())
        features = tokens + [f"{a} {b}" for a, b in zip(tokens, tokens[1:])]
        vector = [0.0] * self._dimensions
        for feature in features:
            digest = hashlib.sha1(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimensions
            vector[index] += 1.0 if digest[4] & 1 else -1.0
        norm = sum(v * v for v in vector) ** 0.5
        return [v / norm for v in vector] if norm else vector


class SafeEmbedder:
    def __init__(self, primary: Embedder) -> None:
        self._primary = primary

    async def embed(self, text: str) -> Optional[List[float]]:
        try:
            vector = await self._primary.embed(text)
        except Exception as exc:
            logger.warning("semantic embedding unavailable: %s", exc.__class__.__name__)
            return None
        return vector or None
