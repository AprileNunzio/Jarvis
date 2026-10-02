import re
import shutil
from pathlib import Path

from config import DEMO

from features.actions.common import SHARES_DIR, my_ip
from features.actions.smb import smb_action
from features.agent import mailer
from features.agent.paths import WORK, resolve
from features.agent.registry import tool

SHARES = (WORK / "condivisioni") if DEMO else SHARES_DIR


def _list(value) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in re.split(r"[,;\s]+", str(value or "")) if v.strip()]


@tool("send_email", "invia un'email, con allegati facoltativi (percorsi di file; le cartelle vengono compresse in .zip)",
      {"to": "indirizzi separati da virgola", "subject": "oggetto", "body": "testo", "attachments": "elenco di percorsi"},
      confirm=True)
async def send_email(to, subject: str, body: str, attachments=None) -> str:
    files = []
    for raw in _list(attachments):
        p = resolve(raw)
        if p.is_dir():
            p = Path(shutil.make_archive(str(p), "zip", root_dir=p.parent, base_dir=p.name))
        if not p.is_file():
            raise ValueError(f"allegato non trovato: {raw}")
        files.append(p)
    how = await mailer.send(_list(to), str(subject or "Da Jarvis")[:200], str(body or ""), files)
    return f"email a {', '.join(_list(to))} {how}" + (f" con {len(files)} allegati" if files else "")


@tool("share_folder", "crea (o verifica) una cartella condivisa SMB sulla rete di casa", {"name": "nome della condivisione"})
async def share_folder(name: str) -> str:
    if DEMO:
        (SHARES / name).mkdir(parents=True, exist_ok=True)
        return f"(demo) cartella condivisa {name} pronta in {SHARES / name}"
    speech, _ = await smb_action(f"crea una cartella condivisa chiamata {name}")
    return speech


@tool("copy_to_share", "copia un file o una cartella in una condivisione SMB (la crea se manca)",
      {"path": "file o cartella", "share": "nome della condivisione"})
async def copy_to_share(path: str, share: str = "condivisa") -> str:
    src = resolve(path)
    target = SHARES / re.sub(r"[^\w\-]", "-", share.lower()).strip("-")
    if not target.exists():
        await share_folder(target.name)
    dest = target / src.name
    if src.is_dir():
        shutil.copytree(src, dest, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dest)
    return f"copiato in {dest}; in rete: \\\\{my_ip()}\\{target.name}\\{src.name}"


@tool("find_contact", "cerca una persona nell'anagrafe di Jarvis e restituisce i suoi indirizzi email", {"name": "nome"})
async def find_contact(name: str) -> str:
    from features.people import people
    wanted = name.lower().strip()
    rows = []
    for p in people.all_profiles():
        label = people.display_name(p)
        if wanted and wanted in label.lower():
            mails = [e.get("address") for e in p.get("emails") or [] if isinstance(e, dict) and e.get("address")]
            rows.append(f"{label}: {', '.join(mails) or 'nessuna email registrata'}")
    return "\n".join(rows) or f"nessuna persona chiamata {name} nell'anagrafe"
