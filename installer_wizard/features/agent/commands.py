import re

from config import env_get

from features.agent.agent import agent

YES = re.compile(r"^\s*(s[iì]|certo|confermo|conferma|procedi|vai|ok|okay|va bene|fallo|esatto|s[iì] grazie)\b", re.I)
NO = re.compile(r"^\s*(no|annulla|lascia stare|ferma|stop|non farlo|aspetta)\b", re.I)
VERB = (r"(crea|creami|scrivi|scrivimi|salva|apri|aprimi|mostra|mostrami|invia|inviami|manda|mandami|spedisci|sposta"
        r"|copia|rinomina|cancella|elimina|avvia|esegui|lancia|imposta|metti|mettiti|togli|togliti|cambia|condividi"
        r"|comprimi|zippa|scarica|prepara|organizza|leggi|leggimi|elenca|trova|cerca|fai|fammi|chiudi|archivia)")
STRONG = re.compile(
    rf"\b{VERB}\w*\b.*\b(e-?mail|mail|posta elettronica|smb|condivis\w*|cartella di rete|allega\w*|zip)\b"
    rf"|\b{VERB}\w*\b[^.?!]*\b(e|poi|quindi|dopo)\s+{VERB}\w*"
    r"|\b(mettiti|togliti|indossa)\b.*\b(cappello|occhiali|cuffie)\b"
    r"|\b(ologramma|avatar)\b.*\b(fai|fa|metti|cambia|imposta|mostra|colore)\b"
    r"|\b(esegui|lancia)\b.*\b(comando|terminale|script)\b"
    r"|\bogni\s+(giorno|mattina|sera|notte|settimana|ora|\d+\s*(minut\w*|or[ae])|luned\w*|marted\w*|mercoled\w*"
    r"|gioved\w*|venerd\w*|sabato|domenica|weekend|fine settimana)\b"
    r"|\b(programmami|pianifica\w*|automatizza\w*)\b|\bprogramma\s+(un|una|ogni|di|che|per)\b"
    r"|\b(compiti|routine|attivit[àa]) programmat\w*"
    r"|\b(cancella|elimina|togli|ferma)\b.*\b(compito|routine|programmazione)\b", re.I)
APPROVE = re.compile(r"^\s*(jarvis[, ]+)?(approva|approvo|autorizz\w+|via libera)\b", re.I)
ALWAYS = re.compile(r"\b(sempre|d'ora in poi|ogni volta)\b", re.I)
REJECT = re.compile(r"^\s*(jarvis[, ]+)?(rifiuta|rifiuto|non approv\w+|nega)\b", re.I)
WEAK = re.compile(
    rf"^\s*(jarvis[, ]+)?(per favore\s+)?{VERB}\w*\b.*\b(file|cartell\w*|directory|documento|progetto|widget|schermo"
    r"|modello|ologramma|avatar|comando|archivio|pagina|percorso|server)\b", re.I)


def enabled() -> bool:
    return env_get("JARVIS_AGENT", "1") != "0"


def _approvals() -> list:
    from features.autonomy import approvals
    return approvals.pending()


def strong(text: str) -> bool:
    if not enabled():
        return False
    if (APPROVE.search(text) or REJECT.search(text)) and _approvals():
        return True
    return agent.has_pending() or bool(STRONG.search(text))


def weak(text: str) -> bool:
    return enabled() and bool(WEAK.search(text))


async def answer(text: str) -> tuple[str, dict]:
    waiting = _approvals()
    if waiting and (APPROVE.search(text) or REJECT.search(text)):
        from features.autonomy.engine import autonomy
        item, yes = waiting[-1], bool(APPROVE.search(text))
        result = await autonomy.approve(item["id"], yes, bool(ALWAYS.search(text)))
        return f"{'Approvato' if yes else 'Rifiutato'}: {item['summary']}. {result}", {"mode": "face"}
    if agent.has_pending():
        if YES.search(text):
            return await agent.confirm(True), {"mode": "face"}
        if NO.search(text):
            return await agent.confirm(False), {"mode": "face"}
        agent.pending = None
    return await agent.run(text), {"mode": "face"}
