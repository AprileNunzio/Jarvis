import re

import httpx

from features.actions.common import sh
from features.agent.paths import FILES
from features.agent.registry import tool

READ_ONLY = re.compile(
    r"^\s*(ls|cat|head|tail|grep|find|df|du|free|uptime|uname|whoami|id|hostname|date|ip\s+(a|addr|r|route|link)"
    r"|ss|ping\s+-c\s*\d|lsblk|lsusb|lspci|ps|top\s+-bn1|systemctl\s+(status|is-active|list-units)|journalctl"
    r"|docker\s+(ps|images|logs)|ollama\s+(list|ps)|nproc|sensors|wc|stat|file|which|echo|pwd)\b[^;&|><`$]*$")
DANGER = re.compile(r"\brm\s+-[a-z]*r[a-z]*f?\s+/(\s|$)|\bmkfs|\bdd\s+if=|:\(\)\s*\{|\bshutdown\b|\bpoweroff\b"
                    r"|\bchmod\s+-R\s+777\s+/(\s|$)|>\s*/dev/sd", re.I)


def _risky(args: dict) -> bool:
    return not READ_ONLY.match(str(args.get("command", "")))


@tool("run_command", "esegue un comando di terminale sul server (bash, 2 minuti al massimo) e ne restituisce l'output",
      {"command": "comando bash"}, confirm=_risky, full_only=True)
async def run_command(command: str) -> str:
    if DANGER.search(command):
        raise PermissionError("comando distruttivo bloccato: non lo eseguo")
    FILES.mkdir(parents=True, exist_ok=True)
    code, out = await sh("bash", "-lc", f"cd {FILES} && {command}", timeout=120)
    return f"codice di uscita {code}\n{out[-5000:]}"


@tool("http_get", "scarica il testo di una pagina web o di un'API pubblica", {"url": "indirizzo http(s)"})
async def http_get(url: str) -> str:
    if not re.match(r"^https?://", url):
        raise ValueError("indirizzo non valido")
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        r = await client.get(url, headers={"User-Agent": "Jarvis/3"})
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", r.text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return f"HTTP {r.status_code}\n" + re.sub(r"\s+", " ", text).strip()[:5000]
