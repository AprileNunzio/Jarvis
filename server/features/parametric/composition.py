import os

from server.config.env import settings
from server.features.llm_gateway.contracts import LLMMessage, LLMRequest
from server.features.llm_gateway.gateway import llm_gateway
from server.features.parametric.application.designer import ParametricDesigner
from server.features.parametric.application.translator import SpecTranslator

_DEFAULT_MODEL = "qwen2.5:7b"


class UnavailableModelError(RuntimeError):
    pass


def build_completion(models_provider, component="parametric_designer"):
    async def complete(system: str, user: str) -> str:
        models = models_provider()
        response = await llm_gateway.generate_completion(
            LLMRequest(
                model_name=(models or [settings.JARVIS_LLM_MODEL or _DEFAULT_MODEL])[0],
                models=models,
                component=component,
                messages=[LLMMessage(role="user", content=user)],
                system_prompt=system,
                temperature=0.1,
                max_tokens=3000,
            )
        )
        if response.is_synthetic:
            raise UnavailableModelError("no language model answered")
        return response.content

    return complete


def build_designer(models_provider=lambda: []) -> ParametricDesigner:
    return ParametricDesigner(SpecTranslator(build_completion(models_provider)), os.path.join(settings.DATA_DIR, "models"))
