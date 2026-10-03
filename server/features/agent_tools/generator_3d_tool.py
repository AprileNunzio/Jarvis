import logging

from server.core.orchestrator.brain_routing import brain_order_for
from server.features.parametric.application.translator import SpecTranslationError
from server.features.parametric.composition import UnavailableModelError, build_designer

logger = logging.getLogger("jarvis.tools.generator_3d")

_designer = build_designer(lambda: brain_order_for("parametric_designer"))


async def generate_3d_model(prompt: str, job_id: str = "react_tool") -> str:
    try:
        result = await _designer.design(prompt, job_id)
    except (SpecTranslationError, UnavailableModelError) as exc:
        logger.warning("3D generation failed: %s", exc)
        return f"Generazione 3D non riuscita: {exc}"
    files = ", ".join(result.written.values())
    return f"Modello {result.spec.name} generato e validato ({len(result.spec.parts)} parti). File: {files}"


def register_3d_tools(react_loop) -> None:
    react_loop.register_tool(
        name="genera_modello_3d",
        description="Genera un modello 3D parametrico (case, oggetti, strutture) in OBJ, DXF e AutoLISP. Input: descrizione testuale dell'oggetto.",
        handler=generate_3d_model,
    )
