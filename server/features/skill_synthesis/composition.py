import os

from server.config.env import settings
from server.core.kernel.consensus.instance import consensus_panel
from server.core.orchestrator.brain_routing import brain_order_for
from server.features.llm_gateway.contracts import LLMMessage, LLMRequest
from server.features.llm_gateway.gateway import llm_gateway
from server.features.self_healing_coder.sandbox_runner import sandbox_gateway
from server.features.skill_synthesis.agents import DynamicToolsAgent, ToolBuilderAgent
from server.features.skill_synthesis.application.runner import DynamicToolRunner
from server.features.skill_synthesis.application.synthesizer import ToolSynthesizer
from server.features.skill_synthesis.infrastructure.consensus_approval import ConsensusApproval
from server.features.skill_synthesis.infrastructure.tool_store import JsonToolStore

_DEFAULT_MODEL = "qwen2.5-coder:7b"


class SynthesisModelUnavailable(RuntimeError):
    pass


async def complete(system: str, user: str) -> str:
    models = brain_order_for("skill_synthesizer")
    response = await llm_gateway.generate_completion(
        LLMRequest(
            model_name=(models or [settings.JARVIS_LLM_MODEL or _DEFAULT_MODEL])[0],
            models=models,
            messages=[LLMMessage(role="user", content=user)],
            system_prompt=system,
            temperature=0.15,
            max_tokens=3000,
        )
    )
    if response.is_synthetic:
        raise SynthesisModelUnavailable("no language model answered")
    return response.content


tool_store = JsonToolStore(os.path.join(settings.DATA_DIR, "dynamic_tools"))
tool_runner = DynamicToolRunner(sandbox_gateway)
tool_synthesizer = ToolSynthesizer(complete, tool_runner, tool_store, ConsensusApproval(consensus_panel))
dynamic_tools_agent = DynamicToolsAgent(tool_store, tool_runner)
tool_builder_agent = ToolBuilderAgent(tool_synthesizer)
