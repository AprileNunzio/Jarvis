import logging
from typing import Any, Dict

from server.features.skill_synthesis.composition import SynthesisModelUnavailable, tool_synthesizer

logger = logging.getLogger("jarvis.skill_synthesis")


class SkillSynthesizerLobe:
    async def synthesize_new_skill(self, request: Dict[str, Any]) -> str:
        intent = request.get("missing_intent", "unknown")
        context = request.get("context", {})
        goal = str(context.get("query") or intent)
        try:
            outcome = await tool_synthesizer.synthesize(goal, {"intent": intent})
        except SynthesisModelUnavailable as exc:
            return f"Sintesi non riuscita: {exc}"
        if not outcome.ok:
            logger.warning("synthesis failed for %s: %s", intent, outcome.message)
            return f"Sintesi non riuscita: {outcome.message}"
        return f"Nuovo strumento «{outcome.tool.name}» creato e verificato in sandbox in {outcome.attempts} tentativi."


skill_synthesizer = SkillSynthesizerLobe()
