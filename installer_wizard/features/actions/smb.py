import re

from state import store

from features.actions.common import my_ip, slug
from features.shares import archive

_SHARE_NAME = re.compile(r"(?:chiamat[oa]|di nome|nominat[oa]|nome)\s+[«\"']?([\w\-]{1,30})", re.I)


async def smb_action(text: str) -> tuple[str, dict]:
    m = _SHARE_NAME.search(text)
    archive.ensure()
    base = archive.folder("scambio")
    name = slug(m.group(1), "cartella") if m else archive.dated("cartella")
    folder = base / name
    created = not folder.exists()
    folder.mkdir(parents=True, exist_ok=True)
    ip = my_ip()
    unc = f"{archive.unc(ip, 'scambio')}\\{name}"
    store.event("INFO", f"Cartella {'creata' if created else 'verificata'} nella condivisione: {unc}", "actions")
    speech = (f"{'Ho creato' if created else 'Esiste già'} la cartella «{name}» nella cartella condivisa di Jarvis, "
              f"in «{archive.FOLDERS['scambio']}». È protetta dalla password dell'utente jarvis-share.")
    return speech, {
        "mode": "focus",
        "title": f"Cartella {name}",
        "subtitle": "Cartella condivisa di Jarvis",
        "panels": [{"type": "kv", "title": "Accesso", "data": {
            "Windows": unc,
            "Mac / Linux": f"smb://{ip}/{archive.SHARE}/{archive.FOLDERS['scambio']}/{name}",
            "Utente": "jarvis-share (password nel pannello, Condivisioni di rete)",
        }}],
    }
