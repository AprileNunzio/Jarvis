import json
import re
from dataclasses import dataclass
from typing import Callable, Mapping

from features.brain.components import BY_ID as COMPONENT_BY_ID
from features.brain.roles import BY_ID as ROLE_BY_ID

MODES = ("inherit", "first", "only")
MAX_ORDER = 12
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,159}$")


class AssignmentError(ValueError):
    pass


@dataclass(frozen=True)
class Assignment:
    role: str = ""
    order: tuple[str, ...] = ()
    mode: str = "inherit"

    @property
    def empty(self) -> bool:
        return not self.role and not self.order

    def to_json(self) -> dict:
        return {"role": self.role, "order": list(self.order), "mode": self.mode}


def parse_assignment(raw: Mapping) -> Assignment:
    role = str(raw.get("role") or "")
    if role and role not in ROLE_BY_ID:
        raise AssignmentError(f"unknown role: {role}")
    refs = raw.get("order") or []
    if not isinstance(refs, (list, tuple)):
        raise AssignmentError("order must be a list")
    order = tuple(dict.fromkeys(str(r).strip() for r in refs if str(r).strip()))
    if len(order) > MAX_ORDER or not all(_REF.match(r) for r in order):
        raise AssignmentError("invalid model list")
    mode = str(raw.get("mode") or ("first" if order else "inherit"))
    if mode not in MODES:
        raise AssignmentError(f"unknown mode: {mode}")
    if mode != "inherit" and not order:
        mode = "inherit"
    return Assignment(role, order, mode)


def parse_all(raw: Mapping) -> dict[str, Assignment]:
    parsed: dict[str, Assignment] = {}
    for component_id, value in raw.items():
        if component_id not in COMPONENT_BY_ID:
            raise AssignmentError(f"unknown component: {component_id}")
        if not isinstance(value, Mapping):
            raise AssignmentError("assignment must be an object")
        assignment = parse_assignment(value)
        if not assignment.empty:
            parsed[component_id] = assignment
    return parsed


def load(text: str) -> dict[str, Assignment]:
    try:
        raw = json.loads(text) if text.strip() else {}
        return parse_all(raw) if isinstance(raw, dict) else {}
    except (ValueError, AssignmentError):
        return {}


def dump(assignments: Mapping[str, Assignment]) -> str:
    return json.dumps({k: v.to_json() for k, v in sorted(assignments.items())}, ensure_ascii=False, separators=(",", ":"))


def effective_role(component_id: str, assignments: Mapping[str, Assignment]) -> str:
    own = assignments.get(component_id)
    return own.role if own and own.role else COMPONENT_BY_ID[component_id].role


def resolve(component_id: str, assignments: Mapping[str, Assignment], role_orders: Mapping[str, list[str]],
            keep: Callable[[str], bool] = lambda ref: True) -> list[str]:
    own = assignments.get(component_id)
    inherited = list(role_orders.get(effective_role(component_id, assignments), []))
    if own and own.order and own.mode == "only":
        chain = list(own.order)
    elif own and own.order:
        chain = [*own.order, *inherited]
    else:
        chain = inherited
    return [ref for ref in dict.fromkeys(chain) if keep(ref)]
