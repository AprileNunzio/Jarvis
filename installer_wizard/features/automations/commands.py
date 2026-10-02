import asyncio
import re

from features.automations.engine import enabled, engine
from features.automations.library import InvalidAutomation, library

FACE = {"mode": "face"}
ANSWER = re.compile(r"^\s*(s[iì]|no|certo|conferm\w*|procedi|vai|ok|okay|va bene|fallo|esatto|annulla|lascia stare|non farlo)\b[\s.!]*\w*[\s.!]*$", re.I)
CREATE = re.compile(r"\b(crea|creami|fai|fammi|prepara|imposta|aggiungi|programma)\s+(un['a]?\s*|una nuova\s+|la\s+)?automazion\w*\b\s*(che|per|:|,)?\s*(.*)$", re.I)
TOGGLE = re.compile(r"\b(attiva|abilita|riattiva|disattiva|disabilita|sospendi)\s+(l['a]\s*)?automazione\s+(.+)$", re.I)
RUN = re.compile(r"\b(esegui|avvia|lancia|fai partire)\s+(l['a]\s*)?automazione\s+(.+)$", re.I)
LIST = re.compile(r"\b(quali|che|elenca|elencami|mostrami)\b.*\bautomazion[ei]\b", re.I)
LATER = re.compile(r"\b(più tardi|dopo|non ora|ne riparliamo|ci penso)\b", re.I)
YES = re.compile(r"^\s*(s[iì]|certo|conferm\w*|procedi|vai|ok|okay|va bene|fallo|esatto)\b", re.I)
STOP = re.compile(r"\b(ferma|interrompi|blocca)\b.*\bautomazion[ei]\b", re.I)


def _summary(a: dict) -> str:
    return f"{len(a['triggers'])} inneschi, {len(a['conditions'])} condizioni, {len(a['actions'])} azioni"


async def _phrase(text: str) -> tuple[str, dict]:
    found = engine.phrase(text)
    if not found:
        raise LookupError
    a, t, words = found
    run = engine.start(a, {**t, "data": words, "label": f"frase «{words['frase']}»"})
    if not run:
        return f"«{a['name']}» non è partita: condizioni non soddisfatte o già in corso, signore.", FACE
    run.chat = True
    for _ in range(40):
        if run.response or run.ended or run.waiting:
            break
        await asyncio.sleep(0.1)
    run.chat = False
    return run.response or t.get("reply") or "Subito, signore.", FACE


async def answer(text: str) -> tuple[str, dict]:
    if not enabled():
        raise LookupError
    if engine.runner.asking and ANSWER.search(text):
        name = engine.runner.answer(text)
        return f"Ricevuto, signore. Proseguo con «{name}».", FACE
    from features.habits.service import habits
    sid = habits.waiting()
    if sid and len(text.split()) <= 6 and (ANSWER.search(text) or LATER.search(text)):
        verdict = "snooze" if LATER.search(text) else "accept" if YES.search(text) else "reject"
        return habits.decide(sid, verdict), FACE
    m = CREATE.search(text)
    if m and m.group(4).strip():
        from features.automations.builder import build
        try:
            spec, errors = await build(m.group(4).strip())
        except Exception as exc:
            return f"Signore, non riesco a progettare l'automazione adesso: {exc}", FACE
        if errors:
            return "Signore, non sono riuscito a costruirla correttamente: " + "; ".join(errors[:3]) + ".", FACE
        spec["enabled"] = False
        try:
            a = library.add(spec, origin="voce")
        except InvalidAutomation as exc:
            return "Signore, l'automazione non è valida: " + "; ".join(exc.errors[:3]), FACE
        return (f"Preparata «{a['name']}»: {_summary(a)}. È disattivata finché non la controlla nel pannello "
                f"Automazioni, oppure mi dica «attiva l'automazione {a['name']}».", FACE)
    m = TOGGLE.search(text)
    if m:
        try:
            return engine.set_enabled(m.group(3).strip(" .!?"), not m.group(1).lower().startswith(("dis", "sosp"))).capitalize() + ", signore.", FACE
        except KeyError:
            return f"Non trovo l'automazione «{m.group(3).strip(' .!?')}», signore.", FACE
    m = RUN.search(text)
    if m:
        try:
            return await engine.start_by_ref(m.group(3).strip(" .!?"), {"type": "manual", "label": "a voce"}) + ", signore.", FACE
        except KeyError:
            return f"Non trovo l'automazione «{m.group(3).strip(' .!?')}», signore.", FACE
    if STOP.search(text) and engine.active:
        n = len(engine.active)
        for rid in list(engine.active):
            engine.stop(rid)
        return f"Fermate {n} automazioni in corso, signore.", FACE
    if LIST.search(text):
        items = library.all()
        if not items:
            return "Non ci sono automazioni, signore. Può crearne una a voce o dal pannello.", FACE
        on = [a["name"] for a in items if a.get("enabled", True)]
        off = len(items) - len(on)
        return (f"{len(items)} automazioni, {len(on)} attive: " + ", ".join(on[:8]) + "." +
                (f" {off} disattivate." if off else "")), FACE
    return await _phrase(text)
