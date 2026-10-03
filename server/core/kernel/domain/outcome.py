from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class NodeResult:
    node_id: str
    output: Dict[str, Any] = field(default_factory=dict)
    speech: str = ""
    agent_id: str = ""


@dataclass(frozen=True)
class ErrorPayload:
    kind: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_prompt(self) -> str:
        return f"[{self.kind}] {self.message}"


@dataclass(frozen=True)
class Verdict:
    accepted: bool
    error: Optional[ErrorPayload] = None

    @classmethod
    def accept(cls) -> "Verdict":
        return cls(True)

    @classmethod
    def reject(cls, kind: str, message: str, **details: Any) -> "Verdict":
        return cls(False, ErrorPayload(kind, message, details))


@dataclass(frozen=True)
class ConsensusVerdict:
    approved: bool
    objections: tuple = ()
