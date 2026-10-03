from typing import Dict, List

from server.config.env import settings

AGENT_BRAIN_ENV: Dict[str, str] = {
    "research": "JARVIS_LLM_RICERCATORE_ORDER",
    "domotics": "JARVIS_LLM_DOMOTICO_ORDER",
    "skill_synthesizer": "JARVIS_LLM_STUDIO_ORDER",
    "genera_modello_3d": "JARVIS_LLM_3D_ORDER",
    "parametric_designer": "JARVIS_LLM_3D_ORDER",
    "agent_self_healing_coder": "JARVIS_LLM_CODER_ORDER",
    "analytic_reasoner": "JARVIS_LLM_DEEP_ORDER",
}


def brain_order_for(agent_id: str) -> List[str]:
    key = AGENT_BRAIN_ENV.get(agent_id)
    raw = getattr(settings, key, "") if key else ""
    return [m.strip() for m in raw.split(",") if m.strip()]


def preferred_brain_for(agent_id: str) -> str:
    order = brain_order_for(agent_id)
    return order[0] if order else ""
