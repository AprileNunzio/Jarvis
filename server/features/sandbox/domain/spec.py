import base64
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping

from server.features.sandbox.domain.errors import SpecError
from server.features.sandbox.domain.strength import Strength

MAX_SOURCE_BYTES = 256 * 1024
MAX_INPUT_FILES = 16
MAX_INPUT_BYTES = 4 * 1024 * 1024
MAX_OUTPUT_BYTES = 8 * 1024 * 1024
MAX_WALL_SECONDS = 300
MAX_MEMORY_MB = 1024
MAX_PIDS = 256
MAX_CPUS = 2.0
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class Language(str, Enum):
    PYTHON = "python"
    BASH = "bash"


class NetworkPolicy(str, Enum):
    NONE = "none"


@dataclass(frozen=True)
class ResourceLimits:
    memory_mb: int = 128
    cpus: float = 0.5
    pids: int = 64
    wall_seconds: int = 30
    output_bytes: int = 1024 * 1024

    def validate(self) -> None:
        if not 16 <= self.memory_mb <= MAX_MEMORY_MB:
            raise SpecError("memory_mb out of range")
        if not 0.1 <= self.cpus <= MAX_CPUS:
            raise SpecError("cpus out of range")
        if not 8 <= self.pids <= MAX_PIDS:
            raise SpecError("pids out of range")
        if not 1 <= self.wall_seconds <= MAX_WALL_SECONDS:
            raise SpecError("wall_seconds out of range")
        if not 1024 <= self.output_bytes <= MAX_OUTPUT_BYTES:
            raise SpecError("output_bytes out of range")


@dataclass(frozen=True)
class ExecutionSpec:
    language: Language
    source: str
    limits: ResourceLimits = field(default_factory=ResourceLimits)
    inputs: Mapping[str, bytes] = field(default_factory=dict)
    network: NetworkPolicy = NetworkPolicy.NONE
    min_strength: Strength = Strength.CONTAINER

    def validate(self) -> None:
        self.limits.validate()
        if not self.source.strip():
            raise SpecError("source is empty")
        if len(self.source.encode("utf-8")) > MAX_SOURCE_BYTES:
            raise SpecError("source too large")
        if len(self.inputs) > MAX_INPUT_FILES:
            raise SpecError("too many input files")
        total = 0
        for name, content in self.inputs.items():
            if not _NAME.match(name):
                raise SpecError(f"invalid input name: {name!r}")
            total += len(content)
        if total > MAX_INPUT_BYTES:
            raise SpecError("inputs too large")

    def to_wire(self) -> Dict[str, Any]:
        return {
            "language": self.language.value,
            "source": self.source,
            "limits": {
                "memory_mb": self.limits.memory_mb,
                "cpus": self.limits.cpus,
                "pids": self.limits.pids,
                "wall_seconds": self.limits.wall_seconds,
                "output_bytes": self.limits.output_bytes,
            },
            "inputs": {n: base64.b64encode(c).decode("ascii") for n, c in self.inputs.items()},
            "network": self.network.value,
            "min_strength": int(self.min_strength),
        }

    @classmethod
    def from_wire(cls, data: Mapping[str, Any]) -> "ExecutionSpec":
        try:
            limits = ResourceLimits(**dict(data.get("limits") or {}))
            inputs = {str(n): base64.b64decode(str(c), validate=True) for n, c in dict(data.get("inputs") or {}).items()}
            spec = cls(
                language=Language(data["language"]),
                source=str(data["source"]),
                limits=limits,
                inputs=inputs,
                network=NetworkPolicy(data.get("network", "none")),
                min_strength=Strength(int(data.get("min_strength", 1))),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SpecError(f"malformed spec: {exc}") from exc
        spec.validate()
        return spec
