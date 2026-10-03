import re

MIN_REPLY_CHARS = 260
MIN_SHOW_REPLY_CHARS = 25
_SHOW = re.compile(
    r"\b(spiegami|spiega|lezione|insegnami|illustra|mostrami|fammi vedere|visualizza|descrivimi|raccontami|come funziona|"
    r"cos'?è|cosa sono|che cos'?è|differenza|confronta|confronto|vantaggi|passaggi|passo passo|procedura|tutorial|schema)\b", re.I)
_TRIVIAL = re.compile(r"^\s*(ciao|grazie|ok|okay|va bene|perfetto|buongiorno|buonasera|buonanotte|salve)\b", re.I)


def worth_planning(question: str, reply: str) -> bool:
    if _TRIVIAL.match(question) and len(question) < 40:
        return False
    if _SHOW.search(question):
        return len(reply.strip()) >= MIN_SHOW_REPLY_CHARS
    return len(reply.strip()) >= MIN_REPLY_CHARS
