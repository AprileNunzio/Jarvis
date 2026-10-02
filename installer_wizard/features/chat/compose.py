import re

_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.*)")


def compose_generic(reply: str, question: str) -> tuple[str, dict]:
    lines = [ln.strip() for ln in reply.splitlines() if ln.strip()]
    bullets = [m.group(1) for ln in lines if (m := _BULLET.match(ln))]
    if len(reply) <= 320 and len(bullets) < 3:
        return reply, {"mode": "face"}

    sentences = re.split(r"(?<=[.!?])\s+", reply.strip())
    speech = " ".join(sentences[:2])
    panels = []
    intro = [ln for ln in lines if not _BULLET.match(ln)]
    if intro:
        panels.append({"type": "text", "title": "Risposta", "body": "\n\n".join(intro)})
    if bullets:
        panels.append({"type": "list", "title": "Punti chiave",
                       "items": [{"label": b, "value": "", "status": ""} for b in bullets]})
    title = question.strip().rstrip("?")
    return speech, {"mode": "focus", "title": title[:80] + ("…" if len(title) > 80 else ""),
                    "subtitle": "Elaborato da Jarvis", "panels": panels}
