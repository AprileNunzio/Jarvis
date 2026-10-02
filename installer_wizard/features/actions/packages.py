import re

from state import store

from features.actions.common import llm, sh

_PKG = re.compile(
    r"\binstalla(?:mi)?\s+(?:il\s+|lo\s+|l'|un\s+)?(?:programma\s+|pacchetto\s+|software\s+|applicazione\s+)?([a-z0-9][a-z0-9.+\-]{1,40})\b",
    re.I,
)


async def package_action(text: str) -> tuple[str, dict]:
    m = _PKG.search(text)
    pkg = m.group(1).lower() if m else ""
    if not pkg or pkg in ("gli", "tutti", "aggiornamenti", "la", "una"):
        raise LookupError("pacchetto non indicato")
    code, _ = await sh("apt-cache", "show", pkg, timeout=30)
    if code != 0:
        guess = await llm(
            f'Qual è il nome esatto del pacchetto Debian/apt per «{pkg}»? Rispondi SOLO con JSON {{"package": "nome"}}',
            as_json=True,
            max_tokens=40,
        )
        alt = re.sub(r"[^a-z0-9.+\-]", "", str(guess.get("package", "")).lower())
        if alt and (await sh("apt-cache", "show", alt, timeout=30))[0] == 0:
            pkg = alt
        else:
            return f"Non esiste un pacchetto chiamato {pkg} nei repository di questo sistema.", {"mode": "face"}
    code, out = await sh("dpkg-query", "-W", "-f=${Status} ${Version}", pkg)
    if code == 0 and "install ok installed" in out:
        return f"{pkg} è già installato, versione {out.split()[-1]}.", {"mode": "face"}
    code, out = await sh("env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y", "-q", pkg, timeout=1200)
    if code != 0:
        return (
            f"L'installazione di {pkg} non è riuscita: {out.splitlines()[-1][:160] if out else 'errore sconosciuto'}",
            {"mode": "face"},
        )
    store.event("INFO", f"Pacchetto installato a voce: {pkg}", "actions")
    return f"Ho installato {pkg}.", {"mode": "face"}
