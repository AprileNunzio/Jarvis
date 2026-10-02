import ast
import math
import operator
import re
import time
from datetime import datetime

TEMPLATE = re.compile(r"\{\{\s*((?:(?!\}\}).)+?)\s*\}\}")
MAX_LEN = 400

BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
          ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: lambda a, b: a ** min(b, 64)}
COMPARE = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt,
           ast.GtE: operator.ge, ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b}
UNARY = {ast.Not: operator.not_, ast.USub: operator.neg, ast.UAdd: operator.pos}


class ExprError(ValueError):
    pass


def number(value, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


class Scope(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def wrap(value):
    if isinstance(value, dict) and not isinstance(value, Scope):
        return Scope({k: wrap(v) for k, v in value.items()})
    if isinstance(value, list):
        return [wrap(v) for v in value]
    return value


def functions(states) -> dict:
    def state(eid, default=""):
        return states.state(str(eid), default)

    def attr(eid, name, default=""):
        return states.attr(str(eid), str(name), default)

    def since(eid):
        return states.since(str(eid))

    def is_state(eid, *values):
        return str(states.state(str(eid))) in [str(v) for v in values]

    def now_hm():
        return datetime.now().strftime("%H:%M")

    return {
        "state": state, "attr": attr, "since": since, "is_state": is_state, "now": time.time, "hm": now_hm,
        "weekday": lambda: datetime.now().weekday(), "hour": lambda: datetime.now().hour,
        "minute": lambda: datetime.now().minute, "today": lambda: datetime.now().strftime("%Y-%m-%d"),
        "num": number, "int": lambda v: int(number(v)), "float": number, "str": str, "bool": bool, "len": len,
        "round": lambda v, d=0: round(number(v), int(d)), "abs": abs, "min": min, "max": max, "sum": sum,
        "lower": lambda s: str(s).lower(), "upper": lambda s: str(s).upper(), "sqrt": lambda v: math.sqrt(number(v)),
        "contains": lambda a, b: str(b).lower() in str(a).lower(), "join": lambda items, sep=", ": sep.join(map(str, items)),
        "present": states.present, "people": states.people, "quiet": states.quiet,
    }


class Evaluator:
    def __init__(self, names: dict) -> None:
        self.names = names
        self.steps = 0

    def run(self, source: str):
        if len(source) > MAX_LEN:
            raise ExprError("espressione troppo lunga")
        try:
            tree = ast.parse(source.strip(), mode="eval")
        except SyntaxError as exc:
            raise ExprError(f"sintassi non valida: {exc.msg}")
        return self.node(tree.body)

    def node(self, n):
        self.steps += 1
        if self.steps > 2000:
            raise ExprError("espressione troppo complessa")
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.Name):
            if n.id in ("true", "True", "vero"):
                return True
            if n.id in ("false", "False", "falso"):
                return False
            if n.id in ("none", "None", "null"):
                return None
            return self.names.get(n.id)
        if isinstance(n, ast.BoolOp):
            if isinstance(n.op, ast.And):
                out = True
                for v in n.values:
                    out = self.node(v)
                    if not out:
                        return out
                return out
            out = False
            for v in n.values:
                out = self.node(v)
                if out:
                    return out
            return out
        if isinstance(n, ast.BinOp) and type(n.op) in BINARY:
            left, right = self.node(n.left), self.node(n.right)
            if isinstance(n.op, ast.Add) and (isinstance(left, str) or isinstance(right, str)):
                return str(left) + str(right)
            if not isinstance(left, (int, float, list)) or not isinstance(right, (int, float)):
                left, right = number(left), number(right)
            try:
                return BINARY[type(n.op)](left, right)
            except ZeroDivisionError:
                raise ExprError("divisione per zero")
        if isinstance(n, ast.UnaryOp) and type(n.op) in UNARY:
            return UNARY[type(n.op)](self.node(n.operand))
        if isinstance(n, ast.Compare):
            left = self.node(n.left)
            for op, comp in zip(n.ops, n.comparators):
                right = self.node(comp)
                a, b = left, right
                if type(op) in (ast.Lt, ast.LtE, ast.Gt, ast.GtE) and not (isinstance(a, str) and isinstance(b, str)):
                    a, b = number(a), number(b)
                if type(op) not in COMPARE or not COMPARE[type(op)](a, b):
                    return False
                left = right
            return True
        if isinstance(n, ast.IfExp):
            return self.node(n.body) if self.node(n.test) else self.node(n.orelse)
        if isinstance(n, ast.Attribute):
            base = self.node(n.value)
            if isinstance(base, dict):
                return base.get(n.attr)
            raise ExprError(f"attributo non accessibile: {n.attr}")
        if isinstance(n, ast.Subscript):
            base, key = self.node(n.value), self.node(n.slice)
            try:
                return base[key]
            except (KeyError, IndexError, TypeError):
                return None
        if isinstance(n, (ast.List, ast.Tuple)):
            return [self.node(x) for x in n.elts]
        if isinstance(n, ast.Dict):
            return {self.node(k): self.node(v) for k, v in zip(n.keys, n.values)}
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            fn = self.names.get(n.func.id)
            if not callable(fn):
                raise ExprError(f"funzione sconosciuta: {n.func.id}")
            return fn(*[self.node(a) for a in n.args])
        raise ExprError(f"costrutto non permesso: {type(n).__name__}")


def evaluate(source: str, names: dict):
    return Evaluator(names).run(str(source))


def render(value, names: dict):
    if isinstance(value, str):
        whole = TEMPLATE.fullmatch(value.strip())
        if whole:
            return evaluate(whole.group(1), names)

        def one(m):
            try:
                out = evaluate(m.group(1), names)
            except ExprError as exc:
                return f"[{exc}]"
            if isinstance(out, float) and out.is_integer():
                out = int(out)
            return "" if out is None else str(out)
        return TEMPLATE.sub(one, value)
    if isinstance(value, dict):
        return {k: render(v, names) for k, v in value.items()}
    if isinstance(value, list):
        return [render(v, names) for v in value]
    return value
