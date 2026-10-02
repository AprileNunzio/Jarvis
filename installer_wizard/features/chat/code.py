import re

FENCE = re.compile(r"```[ \t]*([\w+#.-]*)[^\n]*\n(.*?)(?:```|\Z)", re.S)
HTML = re.compile(r"(<!DOCTYPE html.*?</html>|<html\b.*?</html>|(?:<(?:div|section|style|script|form|table|body|head|ul|svg)\b.*?"
                  r"</(?:div|section|style|script|form|table|body|head|ul|svg)>\s*)+)", re.I | re.S)
ASKED = re.compile(r"\b(codice|code|html|css|javascript|js|python|script|snippet|sorgente|programma|funzione|json|yaml|"
                   r"sql|query|regex|bash|php|java|kotlin|typescript|c\+\+|c#)\b", re.I)
GUESS = [("html", re.compile(r"<\w+[^>]*>", re.S)), ("python", re.compile(r"^\s*(def |import |from \w+ import |class \w+:)", re.M)),
         ("javascript", re.compile(r"\b(const|let|function)\s+\w+|=>", re.S)), ("css", re.compile(r"[.#]?[\w-]+\s*\{[^}]*:[^}]*\}", re.S)),
         ("sql", re.compile(r"^\s*(select|insert|update|create table)\b", re.I | re.M)), ("bash", re.compile(r"^\s*(sudo |apt |cd |ls |#!/)", re.M))]
MAX_CODE = 20000
KEEP = re.compile(r"\b(salva\w*|file|cartell\w*|condivi\w*|pubblic\w*|sito|invia\w*|manda\w*|mail|e-?mail|allega\w*|"
                  r"esegui\w*|lancia\w*|installa\w*|apri\w*\s+(il|la)\s+(file|sito|pagina\s+web))\b", re.I)


def _language(given: str, code: str) -> str:
    if given:
        return given.lower()
    return next((name for name, pattern in GUESS if pattern.search(code)), "testo")


def extract(reply: str, question: str = "") -> tuple[str, list[dict]]:
    blocks = [{"language": _language(m.group(1), m.group(2)), "content": m.group(2).rstrip()}
              for m in FENCE.finditer(reply) if m.group(2).strip()]
    prose = FENCE.sub(" ", reply)
    if not blocks and ASKED.search(question):
        found = [m.group(0).strip() for m in HTML.finditer(reply) if len(m.group(0).strip()) > 20]
        if found:
            blocks = [{"language": "html", "content": "\n\n".join(found)}]
            prose = HTML.sub(" ", reply)
    prose = re.sub(r"\s+", " ", prose).strip(" :")
    return prose, blocks


def answer(reply: str, question: str) -> tuple[str, dict] | None:
    prose, blocks = extract(reply, question)
    if not blocks:
        return None
    language = blocks[0]["language"]
    content = "\n\n".join(b["content"] for b in blocks)[:MAX_CODE]
    sentences = re.split(r"(?<=[.!?])\s+", prose)
    speech = " ".join(sentences[:2]).strip() if prose else ""
    if len(speech) < 3 or len(speech) > 320:
        speech = "Ecco il codice, signore: è sullo schermo."
    title = question.strip().rstrip("?")[:80]
    return speech, {"mode": "face", "code": True, "title": title,
                    "panels": [{"type": "code", "data": {"language": language, "content": content, "title": title}}]}


def wanted(question: str) -> bool:
    return bool(ASKED.search(question)) and not KEEP.search(question)
