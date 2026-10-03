from typing import List, Sequence

from server.core.kernel.consensus.llm_voter import LlmVoter
from server.core.kernel.consensus.panel import ConsensusPanel
from server.core.kernel.consensus.policy_voter import PolicyGuardVoter
from server.core.orchestrator.brain_routing import brain_order_for

_SECURITY = (
    "Sei il responsabile della sicurezza di Jarvis. Valuta se eseguire questo piano può causare perdita di dati, "
    "accessi non autorizzati, modifiche irreversibili al sistema, al git o a transazioni. Approva solo se il piano è sicuro."
)
_PROPORTIONALITY = (
    "Sei il revisore di proporzionalità di Jarvis. Valuta se ogni passo è necessario per l'obiettivo e se il piano "
    "evita azioni distruttive superflue. Approva solo se il piano è minimo e coerente."
)
_REVERSIBILITY = (
    "Sei il revisore della reversibilità di Jarvis. Valuta se ogni modifica potrebbe essere annullata o ripristinata "
    "(backup, cestino, commit separati). Approva solo se un errore resterebbe recuperabile."
)


def pick_models(candidates: Sequence[str], avoid: str, count: int) -> List[List[str]]:
    pool = [m for m in dict.fromkeys(candidates) if m]
    preferred = [m for m in pool if m != avoid] or pool
    if not preferred:
        return [[] for _ in range(count)]
    return [[preferred[i % len(preferred)]] + [m for m in pool if m != preferred[i % len(preferred)]] for i in range(count)]


def build_consensus_panel(planner_model: str = "qwen2.5:7b") -> ConsensusPanel:
    candidates = brain_order_for("analytic_reasoner") + brain_order_for("agent_self_healing_coder")
    security, proportionality, reversibility = pick_models(candidates, planner_model, 3)
    return ConsensusPanel([
        PolicyGuardVoter(),
        LlmVoter("security", _SECURITY, security, can_veto=True),
        LlmVoter("proportionality", _PROPORTIONALITY, proportionality),
        LlmVoter("reversibility", _REVERSIBILITY, reversibility),
    ])
