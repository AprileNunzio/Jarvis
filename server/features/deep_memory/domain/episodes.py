import math
from array import array
from dataclasses import dataclass
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class Episode:
    episode_id: str
    goal: str
    approach: str
    error_kind: str
    error_message: str
    created_at: float
    resolution: str = ""

    @property
    def resolved(self) -> bool:
        return bool(self.resolution)

    def as_text(self) -> str:
        return f"{self.goal}\n{self.approach}\n{self.error_kind}: {self.error_message}"


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def pack(vector: Iterable[float]) -> bytes:
    return array("f", vector).tobytes()


def unpack(blob: bytes) -> List[float]:
    values = array("f")
    values.frombytes(blob)
    return list(values)
