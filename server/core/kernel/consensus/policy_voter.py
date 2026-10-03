import re
from typing import List, Pattern, Tuple

from server.core.kernel.consensus.ballot import Ballot
from server.core.kernel.domain.dag import ExecutionDag

_FORBIDDEN: Tuple[Tuple[str, Pattern[str]], ...] = tuple(
    (label, re.compile(pattern, re.IGNORECASE))
    for label, pattern in (
        ("recursive delete of a root path", r"\brm\s+-[a-z]*r[a-z]*f?[a-z]*\s+['\"]?(/|~|\$home|\*)(?![\w.~-]|/[\w.])"),
        ("filesystem formatting", r"\b(mkfs(\.\w+)?|format\s+[a-z]:)\b"),
        ("raw disk write", r"\bdd\s+[^|;]*\bof=/dev/"),
        ("database destruction", r"\bdrop\s+(database|table|schema)\b|\btruncate\s+table\b"),
        ("history rewrite", r"\bgit\s+(push\s+(-f|--force)|reset\s+--hard|clean\s+-[a-z]*f)"),
        ("permission wipe", r"\bchmod\s+-r\s+0?777\s+/"),
        ("credential access", r"/etc/(shadow|sudoers)|\.ssh/id_|\bprivate[_ ]key\b"),
        ("remote script execution", r"\b(curl|wget)\b[^|;]*\|\s*(sudo\s+)?(ba|z)?sh\b"),
        ("fork bomb", r":\(\)\s*\{\s*:\|:"),
        ("system shutdown", r"\b(shutdown|poweroff|halt)\b\s*(-\w+\s*)*(now|0)?\s*$"),
    )
)


class PolicyGuardVoter:
    name = "policy_guard"
    can_veto = True

    async def vote(self, dag: ExecutionDag) -> Ballot:
        violations: List[str] = []
        for node_id, spec in dag.nodes.items():
            for label, pattern in _FORBIDDEN:
                if pattern.search(spec.description):
                    violations.append(f"{node_id}: {label}")
        if violations:
            return Ballot(self.name, False, "; ".join(violations))
        return Ballot(self.name, True, "no forbidden operation found")
