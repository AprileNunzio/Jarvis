import logging
from typing import List

import httpx
from server.config.env import settings

logger = logging.getLogger("jarvis.embedding_engine")


class OllamaEmbeddingEngine:

    def __init__(
        self,
        ollama_url: str = settings.OLLAMA_BASE_URL,
        default_model: str = settings.JARVIS_EMBED_MODEL,
    ) -> None:
        self._url = ollama_url
        self._model = default_model

    async def ensure_model_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self._url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    names = [m.get("name", "") for m in models]
                    if any(self._model in n for n in names):
                        return True
                    logger.warning(
                        "Model '%s' not found in Ollama. Run: ollama pull %s",
                        self._model,
                        self._model,
                    )
                    return False
        except Exception:
            logger.error("Cannot reach Ollama at %s", self._url)
            return False

    async def embed(self, text: str) -> List[float]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self._url}/api/embeddings", json={"model": self._model, "prompt": text})
            response.raise_for_status()
            vector = response.json().get("embedding", [])
        if not vector:
            raise ValueError("embedding model returned no vector")
        return [float(v) for v in vector]


embedding_engine = OllamaEmbeddingEngine()
