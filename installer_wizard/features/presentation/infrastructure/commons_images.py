import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, List, Mapping, Optional, Sequence

import httpx

from features.presentation.domain.stage import ImageAsset
from features.presentation.infrastructure import cutout, openverse, wikimedia
from features.presentation.infrastructure.image_store import ImageStore
from features.presentation.infrastructure.wikimedia import Candidate

logger = logging.getLogger("jarvis.presentation.images")

MAX_DOWNLOAD_BYTES = 6 * 1024 * 1024
TRIES = 4
FetchJson = Callable[[str, Mapping[str, str]], Awaitable[Mapping]]
FetchBytes = Callable[[str], Awaitable[bytes]]


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    params: Callable[[str], Mapping[str, str]]
    parse: Callable[[Mapping], List[Candidate]]


COMMONS = Source("wikimedia", wikimedia.API, wikimedia.search_params, wikimedia.candidates)
OPENVERSE = Source("openverse", openverse.API, openverse.search_params, openverse.candidates)


def http_fetchers(user_agent: str):
    async def fetch_json(url: str, params: Mapping[str, str]) -> Mapping:
        async with httpx.AsyncClient(timeout=10, headers={"User-Agent": user_agent}) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    async def fetch_bytes(url: str) -> bytes:
        async with httpx.AsyncClient(timeout=12, headers={"User-Agent": user_agent}, follow_redirects=False) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                if not response.headers.get("content-type", "").startswith("image/"):
                    raise ValueError("not an image")
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data += chunk
                    if len(data) > MAX_DOWNLOAD_BYTES:
                        raise ValueError("image too large")
                return bytes(data)

    return fetch_json, fetch_bytes


class CommonsImages:
    def __init__(self, fetch_json: FetchJson, fetch_bytes: FetchBytes, store: ImageStore, route: str,
                 sources: Sequence[Source] = (COMMONS, OPENVERSE)) -> None:
        self._sources = tuple(sources)
        self._json = fetch_json
        self._bytes = fetch_bytes
        self._store = store
        self._route = route.rstrip("/")

    async def find(self, query: str, with_cutout: bool) -> Optional[ImageAsset]:
        for source in self._sources:
            asset = await self._from(source, query, with_cutout)
            if asset:
                return asset
        return None

    async def _from(self, source: Source, query: str, with_cutout: bool) -> Optional[ImageAsset]:
        try:
            payload = await self._json(source.url, source.params(query))
        except (httpx.HTTPError, ValueError) as exc:
            logger.info("%s search failed: %s", source.name, exc)
            return None
        for candidate in source.parse(payload)[:TRIES]:
            png = await self._prepare(candidate, with_cutout)
            if png:
                name = self._store.save(png)
                return ImageAsset(f"{self._route}/{name}", candidate.author or source.name.capitalize(), candidate.license, candidate.page)
        return None

    async def _prepare(self, candidate: Candidate, with_cutout: bool) -> Optional[bytes]:
        try:
            raw = await self._bytes(candidate.thumb)
            return cutout.cut_out(raw) if with_cutout else cutout.normalise(raw)
        except (httpx.HTTPError, ValueError) as exc:
            logger.info("image %s skipped: %s", candidate.title, exc)
            return None
