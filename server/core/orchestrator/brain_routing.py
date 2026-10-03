import json
import os
from typing import Dict, List, Tuple

from server.config.env import settings

AGENT_BRAIN_ENV: Dict[str, str] = {
    "research": "JARVIS_LLM_RICERCATORE_ORDER",
    "domotics": "JARVIS_LLM_DOMOTICO_ORDER",
    "skill_synthesizer": "JARVIS_LLM_STUDIO_ORDER",
    "tool_builder": "JARVIS_LLM_STUDIO_ORDER",
    "genera_modello_3d": "JARVIS_LLM_3D_ORDER",
    "parametric_designer": "JARVIS_LLM_3D_ORDER",
    "agent_self_healing_coder": "JARVIS_LLM_CODER_ORDER",
    "analytic_reasoner": "JARVIS_LLM_DEEP_ORDER",
    "kernel_planner": "JARVIS_LLM_DEEP_ORDER",
    "kernel_critic": "JARVIS_LLM_DEEP_ORDER",
}

_cache: Tuple[int, dict] = (-1, {})


def _routes() -> dict:
    global _cache
    try:
        stamp = os.stat(settings.BRAIN_ROUTES_PATH).st_mtime_ns
    except OSError:
        return {}
    if stamp != _cache[0]:
        try:
            with open(settings.BRAIN_ROUTES_PATH, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            data = {}
        _cache = (stamp, data if isinstance(data, dict) else {})
    return _cache[1]


def _split(raw: str) -> List[str]:
    return [m.strip() for m in (raw or "").split(",") if m.strip()]


def brain_order_for(component_id: str) -> List[str]:
    published = (_routes().get("components") or {}).get(component_id)
    if isinstance(published, list):
        return [str(ref) for ref in published if ref]
    key = AGENT_BRAIN_ENV.get(component_id)
    return _split(getattr(settings, key, "")) if key else []


def has_explicit_brain(component_id: str) -> bool:
    return component_id in (_routes().get("explicit") or [])


def keep_alive_for(model: str, default: str) -> str:
    chosen = (_routes().get("keep_alive") or {}).get(model)
    return str(chosen) if chosen else default


def preferred_brain_for(agent_id: str) -> str:
    order = brain_order_for(agent_id)
    return order[0] if order else ""
