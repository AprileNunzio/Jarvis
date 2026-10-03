from typing import Awaitable, Callable, Optional, Protocol

from features.presentation.domain.stage import ImageAsset

Completion = Callable[[str, str], Awaitable[dict]]


class ImageFinder(Protocol):
    async def find(self, query: str, cutout: bool) -> Optional[ImageAsset]: ...


class ModelBuilder(Protocol):
    def request(self, subject: str) -> None: ...
