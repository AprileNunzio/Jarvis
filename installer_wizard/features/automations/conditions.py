from datetime import datetime

from features.automations import sun
from features.automations.expr import ExprError, evaluate, number, render


def _minutes(hm: str) -> int:
    h, m = str(hm).split(":")
    return int(h) * 60 + int(m)


def in_window(after: str, before: str, days: list | None = None, now: datetime | None = None) -> bool:
    now = now or datetime.now()
    if days and now.weekday() not in [int(d) for d in days]:
        return False
    cur = now.hour * 60 + now.minute
    a = _minutes(after) if after else None
    b = _minutes(before) if before else None
    if a is None and b is None:
        return True
    if a is None:
        return cur < b
    if b is None:
        return cur >= a
    return a <= cur < b if a <= b else cur >= a or cur < b


def compare(left, op: str, right) -> bool:
    if op == "contiene":
        return str(right).lower() in str(left).lower()
    if op == "in":
        return str(left) in [x.strip() for x in str(right).split(",")]
    if op in (">", ">=", "<", "<="):
        a, b = number(left, float("nan")), number(right, float("nan"))
        if a != a or b != b:
            return False
        return {">": a > b, ">=": a >= b, "<": a < b, "<=": a <= b}[op]
    same = str(left).lower() == str(right).lower()
    if not same and number(left, float("nan")) == number(right, float("nan")):
        same = True
    return same if op != "!=" else not same


class Checker:
    def __init__(self, states, names_fn) -> None:
        self.states = states
        self.names = names_fn

    def all(self, conds: list, ctx: dict, trace: list | None = None) -> bool:
        return all(self.one(c, ctx, trace) for c in conds or [])

    def one(self, c: dict, ctx: dict, trace: list | None = None) -> bool:
        try:
            ok = self._eval(c, ctx, trace)
            detail = ""
        except (ExprError, ValueError, TypeError, KeyError) as exc:
            ok, detail = False, f"errore: {exc}"
        if trace is not None:
            trace.append({"kind": "condizione", "type": c.get("type"), "id": c.get("id"), "ok": ok,
                          "detail": detail or self.describe(c)})
        return ok

    def _eval(self, c: dict, ctx: dict, trace) -> bool:
        kind = c.get("type")
        names = self.names(ctx)
        if kind == "and":
            return all(self.one(x, ctx, trace) for x in c.get("conditions") or [])
        if kind == "or":
            return any(self.one(x, ctx, trace) for x in c.get("conditions") or [])
        if kind == "not":
            return not any(self.one(x, ctx, trace) for x in c.get("conditions") or [])
        if kind == "time":
            return in_window(render(c.get("after") or "", names), render(c.get("before") or "", names), c.get("days"))
        if kind == "state":
            eid = render(c["entity"], names)
            st = self.states.get(eid)
            if st is None:
                return False
            value = (st.get("attrs") or {}).get(c["attribute"]) if c.get("attribute") else st.get("state")
            if not compare(value, c.get("op") or "==", render(c.get("value"), names)):
                return False
            hold = number(c.get("for"), 0)
            return not hold or self.states.since(eid) >= hold
        if kind == "presence":
            want = c.get("present", True) is not False
            return self.states.present(render(c.get("person") or "", names)) == want
        if kind == "sun":
            return sun.up() == (c.get("when") == "day")
        if kind == "quiet":
            return self.states.quiet() == (c.get("active", True) is not False)
        if kind == "trigger":
            return str((ctx.get("trigger") or {}).get("id")) == str(c.get("id"))
        if kind == "expr":
            return bool(evaluate(c["expr"], names))
        raise ValueError(f"condizione sconosciuta {kind}")

    @staticmethod
    def describe(c: dict) -> str:
        kind = c.get("type")
        if kind == "state":
            return f"{c.get('entity')}{'.' + c['attribute'] if c.get('attribute') else ''} {c.get('op') or '=='} {c.get('value')}"
        if kind == "time":
            return f"tra {c.get('after') or 'inizio'} e {c.get('before') or 'fine'}"
        if kind == "presence":
            return f"{c.get('person') or 'qualcuno'} {'presente' if c.get('present', True) is not False else 'assente'}"
        if kind == "expr":
            return str(c.get("expr"))
        return kind or ""
