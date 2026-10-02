import re

NUM = r"(\d+(?:[.,]\d+)?)"
PCT = NUM + r"\s*(?:%|per\s*cento)"


def num(s: str) -> float:
    return float(s.replace(",", "."))


def fmt(v: float, money: bool = False) -> str:
    s = f"{v:.2f}" if money else f"{round(v, 4):f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def euro(v: float) -> str:
    return f"{fmt(v, abs(v - round(v)) >= 0.005)} euro"


def run(text: str) -> dict:
    t = text.lower().replace("€", " euro ")
    t = re.sub(r"(\d)\.(\d{3})(?!\d)", r"\1\2", t)
    iva_rate = 22.0
    m = re.search(r"iva\s*(?:al|del)?\s*" + PCT, t) or re.search(PCT + r"\s*(?:di\s+)?iva", t)
    if m:
        iva_rate = num(m.group(1))

    m = re.search(r"scorpor\w*.*?iva.*?" + NUM + r"(?!\s*%)", t) or re.search(NUM + r"(?!\s*%)\s*(?:euro\s*)?iva\s+inclusa", t)
    if m and "iva" in t:
        gross = num(m.group(1))
        net = gross / (1 + iva_rate / 100)
        return {"ok": True, "result": round(net, 2),
                "speech": f"Su {euro(gross)} IVA inclusa al {fmt(iva_rate)}%, l'imponibile è {euro(net)} e l'IVA è {euro(gross - net)}."}

    m = re.search(NUM + r"(?!\s*%)\s*(?:euro\s*)?(?:più|\+)\s*iva", t) or \
        re.search(r"iva\s*(?:al\s*" + PCT + r"\s*)?(?:su|di|a)\s*" + NUM + r"(?!\s*%)", t)
    if m and "iva" in t:
        net = num(m.group(m.lastindex))
        vat = net * iva_rate / 100
        return {"ok": True, "result": round(net + vat, 2),
                "speech": f"{euro(net)} più IVA al {fmt(iva_rate)}% fanno {euro(net + vat)}; l'IVA è {euro(vat)}."}

    discount = None
    m = re.search(r"scont\w*\s*(?:del|di|al)?\s*" + PCT + r"\s*(?:su|da|a|di)\s*" + NUM, t)
    if m:
        discount = (num(m.group(1)), num(m.group(2)))
    else:
        m = re.search(NUM + r"(?!\s*%)\s*(?:euro\s*)?(?:scontat\w*|con\s+(?:lo\s+)?sconto)\s*(?:del|di|al)?\s*" + PCT, t)
        if m:
            discount = (num(m.group(2)), num(m.group(1)))
    if discount:
        pct, price = discount
        cut = price * pct / 100
        return {"ok": True, "result": round(price - cut, 2),
                "speech": f"Con lo sconto del {fmt(pct)}% su {euro(price)} paghi {euro(price - cut)}, risparmi {euro(cut)}."}

    m = re.search(r"(?:aument\w*|maggiorat\w*|ricarico)\s*(?:del|di)?\s*" + PCT + r"\s*(?:su|a|di)\s*" + NUM, t)
    if m:
        pct, base = num(m.group(1)), num(m.group(2))
        return {"ok": True, "result": base * (1 + pct / 100),
                "speech": f"{fmt(base)} aumentato del {fmt(pct)}% fa {fmt(base * (1 + pct / 100))}."}

    m = re.search(r"(?:che|quale)\s+percentuale\s+(?:è|e'|rappresenta)\s+" + NUM + r"\s+(?:di|su|rispetto a)\s+" + NUM, t) or \
        re.search(NUM + r"\s+(?:è|e'|sta)\s+(?:a|su)\s+" + NUM + r"\s+(?:in|come)\s+percentuale", t)
    if m:
        part, whole = num(m.group(1)), num(m.group(2))
        if not whole:
            return {"ok": False, "error": "divisione per zero"}
        return {"ok": True, "result": part / whole * 100,
                "speech": f"{fmt(part)} è il {fmt(part / whole * 100)}% di {fmt(whole)}."}

    m = re.search(PCT + r"\s*(?:di|su)\s*" + NUM, t)
    if m:
        pct, base = num(m.group(1)), num(m.group(2))
        return {"ok": True, "result": base * pct / 100, "speech": f"Il {fmt(pct)}% di {fmt(base)} è {fmt(base * pct / 100)}."}
    return {"ok": False, "error": "nessuna percentuale riconosciuta"}
