import re
from pathlib import Path

from state import store

from features.actions.common import SHARES_DIR, SMB_CONF, my_ip, sh, slug

_SHARE_NAME = re.compile(r"(?:chiamat[oa]|di nome|nominat[oa]|nome)\s+[«\"']?([\w\-]{1,30})", re.I)


async def smb_action(text: str) -> tuple[str, dict]:
    m = _SHARE_NAME.search(text)
    name = slug(m.group(1), "condivisa") if m else "condivisa"
    if not Path("/usr/sbin/smbd").exists():
        code, out = await sh(
            "env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y", "-q", "samba", timeout=900
        )
        if code != 0:
            raise RuntimeError(f"installazione di Samba non riuscita: {out[-200:]}")
    folder = SHARES_DIR / name
    folder.mkdir(parents=True, exist_ok=True)
    folder.chmod(0o2777)
    conf = SMB_CONF.read_text(errors="ignore") if SMB_CONF.exists() else "[global]\n   workgroup = WORKGROUP\n"
    if not re.search(r"^\s*map to guest\s*=", conf, re.M | re.I):
        conf = re.sub(r"^\[global\]\s*$", "[global]\n   map to guest = Bad User", conf, count=1, flags=re.M)
    created = f"[{name}]" not in conf
    if created:
        conf += (
            f"\n[{name}]\n   comment = Cartella condivisa creata da Jarvis\n   path = {folder}\n"
            "   browseable = yes\n   read only = no\n   guest ok = yes\n   force user = nobody\n"
            "   create mask = 0666\n   directory mask = 2777\n"
            "   hosts allow = 127. 10. 172.16.0.0/12 192.168.\n"
        )
        SMB_CONF.write_text(conf)
    code, out = await sh("testparm", "-s", timeout=20)
    if code != 0:
        raise RuntimeError(f"configurazione Samba non valida: {out[-200:]}")
    await sh("systemctl", "enable", "--now", "smbd", timeout=60)
    await sh("systemctl", "reload-or-restart", "smbd", timeout=60)
    _, active = await sh("systemctl", "is-active", "smbd")
    ip = my_ip()
    if active.strip() != "active":
        raise RuntimeError("il servizio Samba non si è avviato")
    store.event("INFO", f"Cartella condivisa SMB {'creata' if created else 'verificata'}: {name}", "actions")
    speech = (
        f"{'Ho creato' if created else 'Esiste già'} la cartella condivisa «{name}». Da Windows apri "
        f"\\\\{ip}\\{name}, da Mac o Linux smb://{ip}/{name}. È accessibile senza password, ma solo dalla "
        "rete di casa."
    )
    return speech, {
        "mode": "focus",
        "title": f"Condivisione {name}",
        "subtitle": "Samba attivo",
        "panels": [
            {
                "type": "kv",
                "title": "Accesso",
                "data": {
                    "Windows": f"\\\\{ip}\\{name}",
                    "Mac / Linux": f"smb://{ip}/{name}",
                    "Cartella": str(folder),
                    "Accesso": "ospite, solo reti private",
                },
            }
        ],
    }
