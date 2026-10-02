import logging
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


embedding_engine = OllamaEmbeddingEngine()
