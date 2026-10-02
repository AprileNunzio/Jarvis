import re

_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.*)")
EXPLAIN_FIRST = re.compile(r"\b(spiega\w*|perch[ée]|come funziona|cos'?è|che cos'?è|differenz\w*|quando si usa|"
                           r"a cosa serve|mi (dici|racconti)|insegna\w*|impara\w*)\b", re.I)
WIDGET_ONLY_EXPLAIN = 140
WIDGET_ONLY_LINES = 25
TITLE_MAX = 80


def _title(question: str) -> str:
    title = question.strip().rstrip("?")
    return title[:TITLE_MAX] + ("…" if len(title) > TITLE_MAX else "")


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def _speech(prose: str, fallback: str) -> str:
    speech = " ".join(_sentences(prose)[:2]).strip(" :")
    return speech if 3 <= len(speech) <= 320 else fallback


def _explanation(prose_lines: list[str]) -> tuple[str, list[str]]:
    bullets = [m.group(1) for ln in prose_lines if (m := _BULLET.match(ln))]
    text = "\n\n".join(ln for ln in prose_lines if not _BULLET.match(ln)).strip(" :")
    return text, bullets


def _measure(blocks: list[dict]) -> tuple[int, int]:
    lines = [ln for b in blocks for ln in b["content"].splitlines()]
    return len(lines), max((len(ln) for ln in lines), default=0)


def _code_spans(explain_len: int, lines: int, width: int) -> tuple[int, int]:
    if width > 90 or lines > 45:
        return 4, 8
    if explain_len > 900:
        return 6, 6
    if explain_len < 300 and lines > 20:
        return 4, 8
    return 5, 7


def plan_code(question: str, prose_lines: list[str], blocks: list[dict], max_code: int) -> tuple[str, dict, str]:
    text, bullets = _explanation(prose_lines)
    flat = re.sub(r"\s+", " ", " ".join(prose_lines)).strip()
    speech = _speech(flat, "Ecco il codice, signore: è sullo schermo.")
    lines, width = _measure(blocks)
    title = _title(question)
    beyond_speech = len(re.sub(r"\s+", " ", text)) - len(speech)
    if len(blocks) == 1 and not bullets and beyond_speech < WIDGET_ONLY_EXPLAIN and lines <= WIDGET_ONLY_LINES:
        block = blocks[0]
        return speech, {"mode": "face", "code": True, "title": title, "panels": [
            {"type": "code", "data": {"language": block["language"], "content": block["content"][:max_code], "title": title}}]}, "code_view"
    explain = [p for p in (
        {"type": "text", "title": "Spiegazione", "body": text} if len(text) > len(speech) + 20 else None,
        {"type": "list", "title": "Punti chiave", "items": [{"label": b, "value": "", "status": ""} for b in bullets]}
        if bullets else None) if p]
    explain_len = len(text) + sum(len(b) for b in bullets)
    code_panels = [{"type": "code", "title": "Codice", "language": b["language"],
                    "content": b["content"][:max_code]} for b in blocks]
    if not explain:
        for p in code_panels:
            p["span"] = 12 if len(code_panels) == 1 or width > 90 else 6
        panels = code_panels
    elif len(code_panels) == 1:
        left, right = _code_spans(explain_len, lines, width)
        main, extra = explain[0], explain[1:]
        main["span"], code_panels[0]["span"] = left, right
        for p in extra:
            p["span"] = 12
        explain_first = EXPLAIN_FIRST.search(question) or explain_len > 400
        panels = ([main, code_panels[0]] if explain_first else [code_panels[0], main]) + extra
    else:
        for p in explain:
            p["span"] = 12 if len(explain) == 1 else 6
        for p in code_panels:
            p["span"] = 12 if width > 90 else 6
        panels = explain + code_panels
    for i, p in enumerate(panels):
        p["order"] = i
    return speech, {"mode": "focus", "code": True, "layout": "grid", "title": title,
                    "subtitle": "Spiegazione e codice" if explain else "Codice", "panels": panels}, "code_focus"


def presence(reply: str, ui: dict) -> str:
    mode, panels = ui.get("mode", "face"), ui.get("panels") or []
    if mode == "focus":
        heavy = any(int(p.get("span") or 12) >= 8 and p.get("type") == "code" for p in panels) or len(panels) >= 3
        return "small" if heavy else "normal"
    if mode != "face":
        return "normal"
    if ui.get("code") or panels:
        return "small"
    words = len(reply.split())
    if words <= 25:
        return "large"
    return "normal" if words <= 60 else "small"


def plan_text(reply: str, question: str) -> tuple[str, dict]:
    lines = [ln.strip() for ln in reply.splitlines() if ln.strip()]
    bullets = [m.group(1) for ln in lines if (m := _BULLET.match(ln))]
    if len(reply) <= 320 and len(bullets) < 3:
        return reply, {"mode": "face"}
    speech = " ".join(_sentences(reply)[:2])
    intro = [ln for ln in lines if not _BULLET.match(ln)]
    body = "\n\n".join(intro)
    panels = []
    if intro:
        panels.append({"type": "text", "title": "Risposta", "body": body})
    if bullets:
        panels.append({"type": "list", "title": "Punti chiave", "items": [{"label": b, "value": "", "status": ""} for b in bullets]})
    if len(panels) == 2:
        longer_text = len(body) >= sum(len(b) for b in bullets)
        panels[0]["span"], panels[1]["span"] = (7, 5) if longer_text else (5, 7)
    else:
        panels[0]["span"] = 12
    return speech, {"mode": "focus", "layout": "grid", "title": _title(question), "subtitle": "Elaborato da Jarvis",
                    "panels": panels}
