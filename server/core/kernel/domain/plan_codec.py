import json
from typing import Any, Dict, List

from server.core.kernel.domain.dag import ExecutionDag
from server.core.kernel.domain.errors import DagError
from server.core.kernel.domain.node import NodeKind, NodeSpec, RiskLevel

_KIND_BY_INTENT: Dict[str, NodeKind] = {
    "AUTONOMOUS_PROGRAMMING": NodeKind.CODE,
    "3D_GENERATION": NodeKind.PARAMETRIC,
    "SYSOPS_AUTOMATION": NodeKind.DESTRUCTIVE_IO,
    "HOME_AUTOMATION": NodeKind.RPA,
    "VISION_SURVEILLANCE": NodeKind.RPA,
}
_DEFAULT_RISK: Dict[NodeKind, RiskLevel] = {
    NodeKind.DESTRUCTIVE_IO: RiskLevel.DESTRUCTIVE,
    NodeKind.RPA: RiskLevel.REVERSIBLE,
    NodeKind.CODE: RiskLevel.REVERSIBLE,
    NodeKind.TOOL_SYNTHESIS: RiskLevel.REVERSIBLE,
    NodeKind.PARAMETRIC: RiskLevel.REVERSIBLE,
    NodeKind.REASONING: RiskLevel.READ_ONLY,
}


def extract_json_array(raw: str) -> List[Dict[str, Any]]:
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end <= start:
        raise DagError("no JSON array found in plan")
    try:
        items = json.loads(raw[start : end + 1])
    except json.JSONDecodeError as exc:
        raise DagError(f"plan is not valid JSON: {exc.msg}") from exc
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        raise DagError("plan must be a list of objects")
    return items


def _node_id(value: Any) -> str:
    return f"n{value}"


def _risk(item: Dict[str, Any], kind: NodeKind) -> RiskLevel:
    declared = str(item.get("risk", "")).upper()
    default = _DEFAULT_RISK[kind]
    try:
        return max(RiskLevel[declared], default) if declared else default
    except KeyError:
        return default


def dag_from_plan(items: List[Dict[str, Any]]) -> ExecutionDag:
    specs: List[NodeSpec] = []
    for index, item in enumerate(items, start=1):
        intent = str(item.get("estimated_intent", "GENERAL_INTELLIGENCE"))
        try:
            kind = NodeKind(str(item["kind"]).lower()) if "kind" in item else _KIND_BY_INTENT.get(intent, NodeKind.REASONING)
        except ValueError as exc:
            raise DagError(f"unknown node kind: {item.get('kind')!r}") from exc
        depends = item.get("depends_on", [])
        if not isinstance(depends, list):
            raise DagError("depends_on must be a list")
        specs.append(
            NodeSpec(
                node_id=_node_id(item.get("step", index)),
                kind=kind,
                description=str(item.get("description", "")),
                depends_on=tuple(_node_id(d) for d in depends),
                risk=_risk(item, kind),
                intent=intent,
            )
        )
    return ExecutionDag.build(specs)
