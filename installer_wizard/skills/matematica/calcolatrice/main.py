import math
import re

WORDS = [
    (r"radice\s+quadrata\s+di", " sqrt "), (r"radice\s+cubica\s+di", " cbrt "), (r"radice\s+di", " sqrt "),
    (r"fattoriale\s+di", " fact "), (r"logaritmo(\s+naturale)?\s+di", " ln "),
    (r"al\s+quadrato", " ^ 2 "), (r"al\s+cubo", " ^ 3 "), (r"elevato\s+alla|alla\s+potenza|alla", " ^ "),
    (r"seconda", "2"), (r"terza", "3"), (r"quarta", "4"),
    (r"per\s*cento|%", " % "), (r"pi\s*greco", " pi "),
    (r"più|piu'|piu|sommat[oa]\s+(a|con)|aggiungi", " + "), (r"meno|sottratt[oa]\s+(a|da)", " - "),
    (r"moltiplicat[oa]\s+per|moltiplicat[oa]|per|x|×|\*", " * "),
    (r"divis[oa](\s+per)?|:|÷", " / "),
]

FILLER = re.compile(r"(?<![a-z])(il|lo|la|i|gli|le|l'|un|una|uno|numero|valore|risultato|e poi|poi|di|del|della|dello)(?![a-z])")
ROUND = re.compile(r",?\s*arrotondat[oa]\s+(?:a|alla|alle)\s+(\d+)\s*(?:cifre\s+)?(?:decimal[ie]|cifre)")
TOKEN = re.compile(r"\s*(\d+(?:[.,]\d+)?|sqrt|cbrt|fact|log10|ln|pi|[-+*/^()%])")
PREC = {"+": 1, "-": 1, "*": 2, "/": 2, "%": 2, "^": 3}
FUNCS = {"sqrt": math.sqrt, "log10": math.log10, "cbrt": lambda v: math.copysign(abs(v) ** (1 / 3), v), "ln": math.log,
         "fact": lambda v: math.factorial(int(v)) if v == int(v) and 0 <= v <= 170 else float("nan")}


def normalize(text: str) -> str:
    t = text.lower()
    t = re.sub(r"^.*?\b(quanto\s+(fa|fanno|è|e'|vale)|calcola(mi)?|risultato\s+di)\b", " ", t)
    t = re.sub(r"(\d)\.(\d{3})(?!\d)", r"\1\2", t)
    t = ROUND.sub(" ", t)
    t = re.sub(r"logaritmo\s+(in\s+)?base\s+10\s+di|log10\s+di", " log10 ", t)
    for pattern, repl in WORDS:
        t = re.sub(rf"(?<![a-z]){pattern}(?![a-z])", repl, t)
    t = FILLER.sub(" ", t)
    t = re.sub(r"(?<=\D),|,(?=\D)", " ", t)
    return t.replace("?", " ").replace("=", " ")


def tokens(expr: str) -> list:
    out, pos = [], 0
    expr = expr.strip()
    while pos < len(expr):
        m = TOKEN.match(expr, pos)
        if not m:
            if expr[pos].isspace():
                pos += 1
                continue
            raise ValueError(f"simbolo non riconosciuto: {expr[pos]}")
        tok = m.group(1)
        out.append(float(tok.replace(",", ".")) if tok[0].isdigit() else tok)
        pos = m.end()
    return out


def evaluate(toks: list) -> float:
    out, ops, prev = [], [], None
    for t in toks:
        if isinstance(t, float) or t == "pi":
            out.append(math.pi if t == "pi" else t)
        elif t in FUNCS:
            ops.append(t)
        elif t == "(":
            ops.append(t)
        elif t == ")":
            while ops and ops[-1] != "(":
                out.append(ops.pop())
            if not ops:
                raise ValueError("parentesi non bilanciate")
            ops.pop()
            if ops and ops[-1] in FUNCS:
                out.append(ops.pop())
        elif t == "%" and (isinstance(prev, float) or prev in (")", "pi")):
            out.append("pct")
        else:
            if t == "-" and (prev is None or prev in PREC or prev == "("):
                out.append(0.0)
            while ops and ops[-1] != "(" and (ops[-1] in FUNCS or PREC[ops[-1]] > PREC[t]
                                              or (PREC[ops[-1]] == PREC[t] and t != "^")):
                out.append(ops.pop())
            ops.append(t)
        prev = t
    while ops:
        op = ops.pop()
        if op == "(":
            raise ValueError("parentesi non bilanciate")
        out.append(op)
    stack = []
    for t in out:
        if isinstance(t, float):
            stack.append(t)
        elif t in FUNCS:
            stack.append(FUNCS[t](stack.pop()))
        elif t == "pct":
            stack.append(stack.pop() / 100)
        else:
            b, a = stack.pop(), stack.pop()
            stack.append({"+": a + b, "-": a - b, "*": a * b, "/": a / b if b else float("inf"),
                          "%": a * b / 100, "^": a ** b if abs(b) < 1000 else float("inf")}[t])
    if len(stack) != 1:
        raise ValueError("espressione incompleta")
    return stack[0]


def fmt(v: float) -> str:
    if v != v or v in (float("inf"), float("-inf")):
        return "indefinito"
    if abs(v) >= 1e15 or (v and abs(v) < 1e-6):
        return f"{v:.6g}".replace(".", ",")
    s = f"{round(v, 6):f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def run(text: str) -> dict:
    expr = normalize(text)
    toks = tokens(expr)
    if not any(isinstance(t, float) for t in toks) or len(toks) < 2:
        return {"ok": False, "error": "nessuna operazione"}
    value = evaluate(toks)
    shown = " ".join(fmt(t) if isinstance(t, float) else t for t in toks)
    m = ROUND.search(text.lower())
    if m and value == value and abs(value) != float("inf"):
        value = round(value, int(m.group(1)))
        return {"ok": True, "result": value, "expression": shown,
                "speech": f"Fa {f'{value:,.{int(m.group(1))}f}'.replace(',', ' ').replace('.', ',').replace(' ', '.')}."}
    return {"ok": True, "result": value, "expression": shown, "speech": f"Fa {fmt(value)}."}
