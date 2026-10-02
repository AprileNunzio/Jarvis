import re
import time
from pathlib import Path

from state import store

from features.actions.common import FILES_DIR, SMB_CONF, llm, my_ip

_FILE_NAME = re.compile(
    r"(?:chiamat[oa]|di nome|nominat[oa])\s+[«\"']?([\w\-. ]{1,60}?\.\w{1,6}|[\w\-.]{1,60})[»\"']?(?=[\s,.:;]|$)", re.I
)
_FILE_BODY = re.compile(
    r"\b(?:con\s+(?:dentro|scritto|il testo|il contenuto|questo contenuto)|contenente|che contiene"
    r"|con)\s*:?\s*[«\"']?(.+?)[»\"']?\s*$",
    re.I | re.S,
)


async def file_action(text: str) -> tuple[str, dict]:
    name_m, body_m = _FILE_NAME.search(text), _FILE_BODY.search(text)
    name = name_m.group(1).strip() if name_m else ""
    body = body_m.group(1).strip() if body_m else ""
    if not name or not body or len(body.split()) > 60 and not re.search(r"con\s+(dentro|scritto)", text, re.I):
        spec = await llm(
            "Dalla richiesta estrai il file da creare. Rispondi SOLO con JSON: "
            '{"filename": "nome.estensione", "content": "contenuto completo del file"}. '
            "Se l'utente detta il testo, copialo fedelmente; se chiede di scriverlo tu, scrivilo completo. "
            "Senza estensione indicata usa .txt.\n\nRichiesta: " + text,
            as_json=True,
            max_tokens=900,
        )
        name = name or str(spec.get("filename") or "")
        body = body or str(spec.get("content") or "")
    name = re.sub(r"[^\w\-. ]", "", Path(name).name).strip(" .") or f"nota-{time.strftime('%Y%m%d-%H%M')}"
    if "." not in name:
        name += ".txt"
    if not body:
        raise LookupError("contenuto del file mancante")
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    path = FILES_DIR / name
    path.write_text(body.rstrip() + "\n", encoding="utf-8")
    ok = path.read_text(encoding="utf-8").strip() == body.strip()
    store.event("INFO", f"File creato: {path}", "actions")
    speech = (
        f"Ho creato il file {name} in {FILES_DIR} con {len(body.splitlines()) or 1} "
        f"{'riga' if len(body.splitlines()) <= 1 else 'righe'} e l'ho verificato."
        if ok
        else f"Ho scritto {path}, ma rileggendolo il contenuto non corrisponde: controllalo."
    )
    if SMB_CONF.exists() and "[file-jarvis]" in SMB_CONF.read_text(errors="ignore"):
        speech += f" Lo trovi anche in rete su \\\\{my_ip()}\\file-jarvis."
    return speech, {
        "mode": "focus",
        "title": name,
        "subtitle": str(path),
        "panels": [{"type": "text", "title": "Contenuto", "body": body[:4000]}],
    }
