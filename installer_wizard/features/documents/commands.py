import re

from config import env_get
from state import store
from tasks import background

from features.desktop.desk import desk
from features.documents import jobs

MAKE = (r"(?!\w*at[oaie]\b)(?:cre[aiou]\w*|fa(?:i|mmi|rmi|resti|rebbe|re)|fammi|gener\w*|prepar\w*|scriv\w*|redig\w*|"
        r"realizz\w*|progett\w*|elabor\w*|impagin\w*|compil\w*|produc\w*)")
WHAT = (r"(document\w*|relazion\w*|lettera|curriculum|cv|contratto|verbale|report|manuale|guida|proposta|offerta|"
        r"preventivo|brochure|volantino|business\s+plan|piano\s+\w+|presentazion\w*|slide|diapositiv\w*|fogli\w*\s+(di\s+)?"
        r"(calcolo|excel)|excel|word|power\s*point|pdf|odt|ods|odp|budget|bilancio|tabella\s+excel|dossier|progetto\s+"
        r"documentale|pacchetto\s+di\s+documenti|documentazione)")
REQUEST = re.compile(rf"\b{MAKE}\b[^.?!]{{0,60}}\b{WHAT}\b", re.I)
LIST = re.compile(r"\b(quali|elenca\w*|mostra\w*|dove\s+(sono|trovo|vedo))\b[^.?!]{0,25}\b(documenti|presentazioni|fogli)\b"
                  r"[^.?!]{0,20}\b(creat\w*|fatt\w*|prepar\w*|tuoi|miei)\b", re.I)
running: dict[str, str] = {}


def enabled() -> bool:
    return env_get("JARVIS_DOCUMENTS", "1") != "0"


def card(entry: dict) -> dict:
    return {"type": "office", "id": entry["id"], "title": entry["title"], "kind": entry["kind"], "summary": entry["summary"],
            "files": entry["files"], "project": entry.get("project", ""), "preview": bool(entry.get("preview")),
            "errors": entry.get("errors", [])}


async def _job(request: str) -> None:
    key = request[:80]
    running[key] = request
    try:
        entry = await jobs.run(request)
    except Exception as exc:
        store.event("WARN", f"Documento non creato: {exc}", "documents")
        desk.show("notice", {"title": "Documenti", "text": f"Non sono riuscito a preparare il documento: {str(exc)[:160]}"}, ttl=30)
        return
    finally:
        running.pop(key, None)
    where = f"nella cartella condivisa, «01 Documenti»{', progetto ' + entry['title'] if entry['kind'] == 'progetto' else ''}"
    speak = (f"Signore, {'il progetto' if entry['kind'] == 'progetto' else 'il documento'} «{entry['title']}» è pronto "
             f"{where}: {entry['summary']}.")
    desk.show("document_viewer", {**card(entry), "announce": True, "speak": speak}, key=f"doc:{entry['id']}", ttl=1800)


async def answer(text: str) -> tuple[str, dict]:
    if not enabled():
        raise LookupError
    if LIST.search(text):
        items = sorted(jobs.load().values(), key=lambda e: e.get("created", 0), reverse=True)[:8]
        if not items:
            return "Non ho ancora preparato documenti, signore.", {"mode": "face"}
        desk.show("document_viewer", card(items[0]), key=f"doc:{items[0]['id']}", ttl=900)
        return ("Gli ultimi: " + "; ".join(f"{e['title']} ({e['summary']})" for e in items[:5]) +
                ". Sono nella cartella condivisa, in «01 Documenti».", {"mode": "face"})
    if not REQUEST.search(text):
        raise LookupError
    background(_job(text))
    project = jobs.wants_project(text)
    return (f"Subito, signore. Preparo {'il progetto con tutti i documenti collegati' if project else 'il documento'}: "
            "ci vorrà qualche minuto, la avviso appena è pronto.", {"mode": "face"})
