import asyncio
import logging
from typing import Optional, Tuple

from config import STATE_DIR
from tasks import background

from features.brain.llm import generate
from features.presentation.application.gate import worth_planning
from features.presentation.application.planner import PresentationPlanner
from features.presentation.infrastructure.commons_images import CommonsImages, http_fetchers
from features.presentation.infrastructure.image_store import ImageStore
from features.study.constants import USER_AGENT

logger = logging.getLogger("jarvis.presentation")

ROUTE = "/api/presentation/image"
BUDGET_SECONDS = 45.0
image_store = ImageStore(STATE_DIR / "presentation" / "images")


class _Models:
    def request(self, subject: str) -> None:
        from features.models3d.commands import _build
        background(_build(subject))


async def _complete(system: str, user: str) -> dict:
    return await generate(user, as_json=True, system=system, max_tokens=1800, temperature=0.2, kind="chat",
                          component="presentation", timeout=60)


_fetch_json, _fetch_bytes = http_fetchers(USER_AGENT)
planner = PresentationPlanner(_complete, CommonsImages(_fetch_json, _fetch_bytes, image_store, ROUTE), _Models())


async def compose(question: str, reply: str) -> Optional[Tuple[str, dict]]:
    if not worth_planning(question, reply):
        return None
    try:
        outcome = await asyncio.wait_for(planner.compose(question, reply), BUDGET_SECONDS)
    except asyncio.TimeoutError:
        logger.info("presentation planning timed out")
        return None
    if outcome is None:
        return None
    if outcome.ui.get("mode") == "face":
        return reply, {"mode": "face"}
    return outcome.speech, outcome.ui
