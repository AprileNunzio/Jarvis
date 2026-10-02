import re
import shlex

from features.actions.common import llm, note_gap, sh

SAFE_CMDS = {
    "ip",
    "ss",
    "df",
    "free",
    "uptime",
    "uname",
    "lsblk",
    "lsusb",
    "lspci",
    "hostname",
    "hostnamectl",
    "ping",
    "dig",
    "nslookup",
    "host",
    "cat",
    "systemctl",
    "journalctl",
    "docker",
    "nmcli",
    "iw",
    "sensors",
    "who",
    "w",
    "ps",
    "date",
    "timedatectl",
    "nproc",
    "getent",
    "traceroute",
    "tracepath",
    "nmap",
    "arp",
    "lscpu",
    "du",
    "ls",
    "findmnt",
    "curl",
    "whois",
    "ollama",
    "last",
    "id",
    "env",
    "smbstatus",
    "avahi-browse",
    "nmblookup",
    "resolvectl",
    "wc",
    "head",
    "tail",
    "grep",
    "stat",
    "file",
    "dpkg",
    "apt",
}
_SAFE_SUB = {
    "systemctl": {"status", "is-active", "is-enabled", "list-units", "list-timers", "--failed"},
    "docker": {"ps", "images", "stats", "logs", "info", "version"},
    "apt": {"list", "show", "policy", "search"},
    "dpkg": {"-l", "-s", "-L"},
    "ollama": {"list", "ps", "show"},
    "ip": {"a", "addr", "r", "route", "link", "neigh", "-br", "-4", "-6", "-s"},
}
_CAT_OK = re.compile(
    r"^/(proc/(cpuinfo|meminfo|loadavg|uptime|version|mounts|net/\w+)|etc/(os-release|hostname|resolv\.conf|hosts|debian_version|timezone|fstab))$"
)


def _command_ok(argv: list[str]) -> bool:
    if not argv or argv[0] not in SAFE_CMDS:
        return False
    if any(re.search(r"[;&|`$<>]", a) for a in argv):
        return False
    if argv[0] in _SAFE_SUB and not any(a in _SAFE_SUB[argv[0]] for a in argv[1:2]) and len(argv) > 1:
        return False
    if argv[0] == "cat" and not all(_CAT_OK.match(a) for a in argv[1:]):
        return False
    if argv[0] == "curl" and not all(a.startswith(("-s", "-I", "-m", "http")) for a in argv[1:]):
        return False
    if argv[0] == "env" and len(argv) > 1:
        return False
    if argv[0] in ("head", "tail", "grep", "wc", "stat", "file", "ls", "du") and any(
        a.startswith(("/etc/jarvis", "/var/lib/jarvis", "/root", "/etc/shadow")) for a in argv[1:]
    ):
        return False
    return True


async def diagnose_action(text: str) -> tuple[str, dict] | None:
    history = ""
    for attempt in range(3):
        spec = await llm(
            "Sei l'amministratore di un server Debian 12 (Jarvis). Per rispondere alla richiesta scegli UN comando "
            "Linux di SOLA LETTURA tra: " + ", ".join(sorted(SAFE_CMDS)) + ". Niente pipe, redirezioni, sudo o "
            "variabili. Se la richiesta non riguarda il sistema, la rete o l'hardware rispondi "
            '{"command": ""}. Rispondi SOLO con JSON {"command": "..."}.' + history + "\n\nRichiesta: " + text,
            as_json=True,
            max_tokens=80,
        )
        cmd = str(spec.get("command") or "").strip()
        if not cmd:
            return None
        try:
            argv = shlex.split(cmd)
        except ValueError:
            argv = []
        if not _command_ok(argv):
            history += f"\nIl comando «{cmd}» non è ammesso: scegline un altro."
            continue
        code, out = await sh(*argv, timeout=60)
        if code == 127 or (code != 0 and not out):
            history += f"\nIl comando «{cmd}» non ha funzionato (codice {code}): scegline un altro."
            continue
        answer = await llm(
            "Rispondi in italiano alla richiesta usando SOLO i dati dell'output del comando qui sotto. Sii preciso "
            "e conciso (massimo 3 frasi), riporta i numeri esatti, non inventare nulla.\n\n"
            f"Richiesta: {text}\nComando: {cmd}\nOutput:\n{out[:3500]}",
            max_tokens=260,
            temperature=0.1,
        )
        return answer, {
            "mode": "focus",
            "title": "Diagnostica",
            "subtitle": f"$ {cmd}",
            "panels": [
                {"type": "text", "title": "Risposta", "body": answer},
                {"type": "text", "title": "Output del comando", "body": out[:3000]},
            ],
        }
    note_gap(text, "nessun comando adatto trovato")
    return None
