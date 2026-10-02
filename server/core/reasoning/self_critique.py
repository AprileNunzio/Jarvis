import json
import logging
from server.features.llm_gateway.gateway import llm_gateway
from server.features.llm_gateway.contracts import LLMRequest, LLMMessage

logger = logging.getLogger("jarvis.self_critique")


class SelfCritiqueEngine:

    def __init__(self, model_name: str = "qwen2.5:7b") -> None:
        self._model = model_name

    async def critique_and_refine(
        self,
        task: str,
        draft_output: str,
        max_refinements: int = 2,
        quality_threshold: int = 8,
    ) -> str:
        current = draft_output

        for attempt in range(1, max_refinements + 1):
            logger.info("Self-critique attempt %d/%d", attempt, max_refinements)

            critique_response = await llm_gateway.generate_completion(
                LLMRequest(
                    model_name=self._model,
                    messages=[
                        LLMMessage(
                            role="user",
                            content=(
                                f"Rivedi criticamente questo output generato per il task:\n"
                                f'"{task}"\n\n'
                                f"Output da rivedere:\n{current}\n\n"
                                "Rispondi con un JSON valido:\n"
                                "{\n"
                                '  "score": <1-10>,\n'
                                '  "issues": ["lista di problemi"],\n'
                                '  "needs_refinement": true/false,\n'
                                '  "refined_output": "output migliorato (solo se needs_refinement=true)"\n'
                                "}"
                            ),
                        )
                    ],
                    system_prompt=(
                        "Sei un revisore perfezionista. Valuta la qualità dell'output:\n"
                        "- Correttezza logica e fattuale\n"
                        "- Completezza rispetto al task richiesto\n"
                        "- Chiarezza e precisione\n"
                        "- Assenza di errori o sviste\n"
                        "Sii severo ma costruttivo. Rispondi SOLO con il JSON."
                    ),
                    temperature=0.3,
                )
            )

            try:
                raw = critique_response.content.strip()
                start = raw.find("{")
                end = raw.rfind("}")
                if start != -1 and end != -1:
                    review = json.loads(raw[start : end + 1])
                else:
                    logger.warning("Self-critique returned non-JSON, keeping current output")
                    return current

                score = review.get("score", 10)
                issues = review.get("issues", [])
                needs_refinement = review.get("needs_refinement", False)

                logger.info(
                    "Self-critique score: %d/10, issues: %s, needs_refinement: %s",
                    score,
                    issues,
                    needs_refinement,
                )

                if not needs_refinement or score >= quality_threshold:
                    return current

                refined = review.get("refined_output", "")
                if refined and len(refined.strip()) > 10:
                    current = refined
                else:
                    logger.warning("Refined output too short or empty, keeping current")
                    return current

            except json.JSONDecodeError:
                logger.warning("Self-critique JSON parse failed, keeping current output")
                return current

        return current


self_critique_engine = SelfCritiqueEngine()
