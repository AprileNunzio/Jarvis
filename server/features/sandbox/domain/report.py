import base64
from dataclasses import dataclass
from typing import Any, Mapping, Tuple


@dataclass(frozen=True)
class Artifact:
    name: str
    content: bytes


@dataclass(frozen=True)
class ExecutionReport:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    oom_killed: bool
    backend: str
    strength: int
    duration_ms: int = 0
    artifacts: Tuple[Artifact, ...] = ()
    artifacts_truncated: bool = False
    egress_denied: Tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.oom_killed

    def to_wire(self) -> dict:
        return {
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "oom_killed": self.oom_killed,
            "backend": self.backend,
            "strength": self.strength,
            "duration_ms": self.duration_ms,
            "artifacts": {a.name: base64.b64encode(a.content).decode("ascii") for a in self.artifacts},
            "artifacts_truncated": self.artifacts_truncated,
            "egress_denied": list(self.egress_denied),
        }

    @classmethod
    def from_wire(cls, data: Mapping[str, Any]) -> "ExecutionReport":
        artifacts = tuple(Artifact(str(n), base64.b64decode(str(c))) for n, c in dict(data.get("artifacts") or {}).items())
        return cls(
            exit_code=int(data["exit_code"]),
            stdout=str(data.get("stdout", "")),
            stderr=str(data.get("stderr", "")),
            timed_out=bool(data.get("timed_out", False)),
            oom_killed=bool(data.get("oom_killed", False)),
            backend=str(data.get("backend", "")),
            strength=int(data.get("strength", 0)),
            duration_ms=int(data.get("duration_ms", 0)),
            artifacts=artifacts,
            artifacts_truncated=bool(data.get("artifacts_truncated", False)),
            egress_denied=tuple(str(h) for h in data.get("egress_denied") or ()),
        )
