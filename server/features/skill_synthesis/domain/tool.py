import re
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Tuple

from server.features.sandbox.domain.spec import MAX_EGRESS_HOSTS, MAX_SOURCE_BYTES, Language, valid_egress_host

TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]{2,40}$")
PARAMETER = re.compile(r"^[a-z][a-z0-9_]{0,30}$")
MAX_PARAMETERS = 12
MAX_DESCRIPTION = 300


class ToolError(ValueError):
    pass


@dataclass(frozen=True)
class DynamicTool:
    name: str
    description: str
    language: Language
    source: str
    parameters: Tuple[str, ...] = ()
    egress_hosts: Tuple[str, ...] = ()
    test_input: Mapping[str, Any] = field(default_factory=dict)
    created_at: float = 0.0

    def validate(self) -> "DynamicTool":
        if not TOOL_NAME.match(self.name):
            raise ToolError("name must be 3-41 lowercase letters, digits or underscores, starting with a letter")
        if not self.description.strip() or len(self.description) > MAX_DESCRIPTION:
            raise ToolError(f"description must be 1-{MAX_DESCRIPTION} characters")
        if not self.source.strip() or len(self.source.encode("utf-8")) > MAX_SOURCE_BYTES:
            raise ToolError("source is empty or too large")
        if len(self.parameters) > MAX_PARAMETERS or not all(PARAMETER.match(p) for p in self.parameters):
            raise ToolError("parameters must be lowercase identifiers")
        if len(self.egress_hosts) > MAX_EGRESS_HOSTS or not all(valid_egress_host(h) for h in self.egress_hosts):
            raise ToolError("egress_hosts must be at most 8 valid host names or *.domain patterns")
        if not isinstance(self.test_input, Mapping):
            raise ToolError("test_input must be an object")
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "language": self.language.value,
            "source": self.source,
            "parameters": list(self.parameters),
            "egress_hosts": list(self.egress_hosts),
            "test_input": dict(self.test_input),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DynamicTool":
        try:
            tool = cls(
                name=str(data["name"]),
                description=str(data["description"]),
                language=Language(data["language"]),
                source=str(data["source"]),
                parameters=tuple(str(p) for p in data.get("parameters") or ()),
                egress_hosts=tuple(str(h).lower() for h in data.get("egress_hosts") or ()),
                test_input=dict(data.get("test_input") or {}),
                created_at=float(data.get("created_at", 0.0)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ToolError(f"malformed tool: {exc}") from exc
        return tool.validate()
