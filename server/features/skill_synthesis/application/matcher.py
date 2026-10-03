import re
from typing import Iterable, Optional, Tuple

from server.features.skill_synthesis.domain.tool import DynamicTool

_WORD = re.compile(r"[a-zà-ú0-9]{3,}")
_STOP = frozenset("""che con del della delle dei degli per una uno gli come sono non the and for with from this that quale quali
dammi dimmi fammi fare voglio vorrei puoi potresti cosa cose molto anche sulla sulle nella nelle dello""".split())


def tokens(text: str) -> frozenset:
    return frozenset(w for w in _WORD.findall(text.lower().replace("_", " ")) if w not in _STOP)


def score(tool: DynamicTool, query: str) -> float:
    overlap = len(tokens(query) & tokens(f"{tool.name} {tool.description}"))
    return min(0.9, 0.25 + 0.2 * overlap) if overlap else 0.0


def best_match(tools: Iterable[DynamicTool], query: str) -> Tuple[Optional[DynamicTool], float]:
    ranked = sorted(((score(t, query), t) for t in tools), key=lambda pair: pair[0], reverse=True)
    if not ranked or ranked[0][0] <= 0:
        return None, 0.0
    return ranked[0][1], ranked[0][0]
