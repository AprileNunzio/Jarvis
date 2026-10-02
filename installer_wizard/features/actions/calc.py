import ast
import math
import re

from features.actions.common import fmt_num, llm, log
from features.brain.llm import BrainUnavailable

_MATH_FUNCS = {
    name: getattr(math, name)
    for name in (
        "sqrt",
        "log",
        "log10",
        "log2",
        "exp",
        "sin",
        "cos",
        "tan",
        "asin",
        "acos",
        "atan",
        "sinh",
        "cosh",
        "tanh",
        "floor",
        "ceil",
        "factorial",
        "gcd",
        "lcm",
        "degrees",
        "radians",
        "hypot",
        "comb",
        "perm",
        "fabs",
    )
}
_MATH_FUNCS.update(
    abs=abs, round=round, min=min, max=max, sum=sum, pow=pow, cbrt=lambda v: math.copysign(abs(v) ** (1 / 3), v)
)
_MATH_CONST = {"pi": math.pi, "e": math.e, "tau": math.tau}
_BIN = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a**b if abs(b) <= 10000 else float("inf"),
}


def safe_eval(expr: str) -> float:
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
            return _BIN[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            v = ev(node.operand)
            return -v if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.Name) and node.id in _MATH_CONST:
            return _MATH_CONST[node.id]
        if isinstance(node, (ast.List, ast.Tuple)):
            return [ev(x) for x in node.elts]
        if isinstance(node, ast.Call) and not node.keywords:
            fn = node.func
            name = (
                fn.attr
                if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id == "math"
                else fn.id
                if isinstance(fn, ast.Name)
                else None
            )
            if name in _MATH_FUNCS:
                return _MATH_FUNCS[name](*[ev(a) for a in node.args])
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "math"
            and node.attr in _MATH_CONST
        ):
            return _MATH_CONST[node.attr]
        raise ValueError(f"elemento non ammesso: {ast.dump(node)[:60]}")

    if len(expr) > 400:
        raise ValueError("espressione troppo lunga")
    value = ev(ast.parse(expr.strip(), mode="eval"))
    if isinstance(value, list) or not isinstance(value, (int, float)):
        raise ValueError("il risultato non è un numero")
    return value


_DECIMALS = re.compile(r"(\d+)\s*(?:cifre\s+)?decimal[ie]", re.I)


async def calc_action(text: str) -> tuple[str, dict]:
    prompt = (
        "Traduci il problema in UNA espressione Python che ne calcola il risultato numerico finale.\n"
        "Puoi usare solo numeri, + - * / // % **, parentesi e le funzioni math.sqrt, math.log (logaritmo "
        "naturale), math.log10, math.exp, math.sin, math.cos, math.tan (in radianti: per i gradi usa "
        "math.radians), math.factorial, math.pi, round, abs.\n"
        "Le percentuali diventano decimali (3,5% → 0.035). Le virgole italiane sono decimali (3,5 → 3.5).\n"
        'Rispondi SOLO con JSON: {"expression": "...", "unit": "unità del risultato o stringa vuota"}\n\n'
        f"Problema: {text}"
    )
    spec, value, expr = {}, None, ""
    for attempt in range(2):
        spec = await llm(
            prompt if not attempt else prompt + f"\n\nL'espressione «{expr}» non era valida: correggila.",
            as_json=True,
            max_tokens=220,
        )
        expr = str(spec.get("expression", "")).replace("^", "**")
        try:
            value = safe_eval(expr)
            break
        except (ValueError, SyntaxError, TypeError, ZeroDivisionError, OverflowError) as exc:
            log.info("Espressione non valida %r: %s", expr, exc)
    if value is None:
        raise LookupError("calcolo non traducibile")
    unit = str(spec.get("unit") or "").strip()
    if len(unit) > 12 or " " in unit.strip():
        unit = ""
    m = _DECIMALS.search(text)
    decimals = int(m.group(1)) if m else (2 if unit.lower() in ("€", "euro", "eur", "$", "dollari") else None)
    shown = fmt_num(round(value, decimals) if decimals is not None else value, decimals)
    speech = f"Il risultato è {shown}{' ' + unit if unit else ''}."
    return speech, {
        "mode": "focus",
        "title": "Calcolo",
        "subtitle": "Espressione verificata ed eseguita da Jarvis",
        "panels": [
            {"type": "kv", "title": "Risultato", "data": {"Risultato": f"{shown} {unit}".strip(), "Espressione": expr}}
        ],
    }


async def try_calc(text: str) -> tuple[str, dict] | None:
    try:
        return await calc_action(text)
    except (LookupError, BrainUnavailable):
        return None
