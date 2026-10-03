import time
import uuid
from typing import Callable, List, Optional, Tuple

from server.features.deep_memory.application.embedders import HashingEmbedder, SafeEmbedder
from server.features.deep_memory.application.ports import Embedder, EpisodeStore
from server.features.deep_memory.domain.episodes import Episode, cosine

SEMANTIC_THRESHOLD = 0.80
LEXICAL_THRESHOLD = 0.55
DUPLICATE_THRESHOLD = 0.97
_FIELD_LIMIT = 400


class FailureIndex:
    def __init__(
        self,
        store: EpisodeStore,
        semantic: Optional[Embedder] = None,
        lexical: Optional[Embedder] = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._store = store
        self._semantic = SafeEmbedder(semantic) if semantic else None
        self._lexical = lexical or HashingEmbedder()
        self._clock = clock

    async def record(self, goal: str, approach: str, error_kind: str, error_message: str) -> Episode:
        episode = Episode(
            episode_id=uuid.uuid4().hex,
            goal=goal[:_FIELD_LIMIT],
            approach=approach[:_FIELD_LIMIT],
            error_kind=error_kind,
            error_message=error_message[:_FIELD_LIMIT],
            created_at=self._clock(),
        )
        semantic, lexical = await self._vectors(episode.as_text())
        duplicate = self._duplicate_of(episode, lexical)
        if duplicate is not None:
            return duplicate
        self._store.add(episode, semantic, lexical)
        return episode

    def resolve(self, episode_id: str, resolution: str) -> bool:
        return self._store.mark_resolved(episode_id, resolution[:_FIELD_LIMIT])

    async def similar(self, text: str, limit: int = 3) -> List[Tuple[Episode, float]]:
        semantic, lexical = await self._vectors(text)
        scored: List[Tuple[Episode, float]] = []
        for episode, stored_semantic, stored_lexical in self._store.all_vectors():
            if semantic is not None and stored_semantic is not None and len(semantic) == len(stored_semantic):
                score = cosine(semantic, stored_semantic)
                threshold = SEMANTIC_THRESHOLD
            else:
                score = cosine(lexical, stored_lexical)
                threshold = LEXICAL_THRESHOLD
            if score >= threshold:
                scored.append((episode, score))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:limit]

    async def warnings_for(self, goal: str, limit: int = 3) -> List[str]:
        lines: List[str] = []
        for episode, _ in await self.similar(goal, limit):
            if episode.resolved:
                lines.append(f"Soluzione già trovata in passato: {episode.resolution}")
            else:
                approach = f" con «{episode.approach[:160]}»" if episode.approach else ""
                lines.append(f"Vicolo cieco noto: era già fallito{approach} ({episode.error_kind}: {episode.error_message[:160]}). Non ripeterlo.")
        return lines

    async def _vectors(self, text: str) -> Tuple[Optional[List[float]], List[float]]:
        semantic = await self._semantic.embed(text) if self._semantic else None
        return semantic, await self._lexical.embed(text)

    def _duplicate_of(self, episode: Episode, lexical: List[float]) -> Optional[Episode]:
        for existing, _, stored_lexical in self._store.all_vectors():
            if not existing.resolved and existing.error_kind == episode.error_kind and cosine(lexical, stored_lexical) >= DUPLICATE_THRESHOLD:
                return existing
        return None
