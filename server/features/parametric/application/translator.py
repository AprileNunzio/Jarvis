import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from pydantic import ValidationError

from server.features.parametric.domain.spec_document import parse_spec_document
from server.features.parametric.domain.schema import ModelSpec, first_error_lines, spec_prompt_description

logger = logging.getLogger("jarvis.parametric.translator")

Completion = Callable[[str, str], Awaitable[str]]

_SYSTEM = (
    "Sei il progettista parametrico di Jarvis. Traduci la richiesta dell'utente in una specifica geometrica "
    "esatta. Scegli tu le dimensioni realistiche, nelle unità indicate, e componi l'oggetto con le primitive "
    "disponibili. Non scrivere codice né spiegazioni.\n"
)


class SpecTranslationError(Exception):
    pass


@dataclass(frozen=True)
class TranslatedSpec:
    spec: ModelSpec
    attempts: int


class SpecTranslator:
    def __init__(self, complete: Completion, max_attempts: int = 3) -> None:
        self._complete = complete
        self._max_attempts = max_attempts

    async def translate(self, intent: str, hint: Optional[str] = None) -> TranslatedSpec:
        system = _SYSTEM + spec_prompt_description()
        request = intent if not hint else f"{intent}\n\nNota: {hint}"
        problem = ""
        for attempt in range(1, self._max_attempts + 1):
            raw = await self._complete(system, request if not problem else f"{request}\n\nLa specifica precedente era invalida: {problem}\nCorreggila.")
            try:
                return TranslatedSpec(self._parse(raw), attempt)
            except (ValueError, ValidationError) as exc:
                problem = first_error_lines(exc) or str(exc)
                logger.warning("spec attempt %d rejected: %s", attempt, problem)
        raise SpecTranslationError(f"no valid specification after {self._max_attempts} attempts: {problem}")

    @staticmethod
    def _parse(raw: str) -> ModelSpec:
        return ModelSpec.model_validate(parse_spec_document(raw))
