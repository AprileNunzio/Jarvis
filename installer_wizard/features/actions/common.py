import asyncio
import json
import logging
import re
import socket
import time
import unicodedata
from pathlib import Path

from config import STATE_DIR

log = logging.getLogger("jarvis.actions")


WORK_DIR = Path("/srv/jarvis")
FILES_DIR = WORK_DIR / "file"
SITES_DIR = WORK_DIR / "siti"
SHARES_DIR = WORK_DIR / "condivisioni"
SMB_CONF = Path("/etc/samba/smb.conf")
GAPS_FILE = STATE_DIR / "skill_gaps.json"


async def sh(*cmd: str, timeout: float = 60) -> tuple[int, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
    except FileNotFoundError:
        return 127, f"comando non trovato: {cmd[0]}"
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, "tempo scaduto"
    return proc.returncode or 0, out.decode("utf-8", "replace").strip()


def slug(text: str, fallback: str = "jarvis") -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:40] or fallback


def my_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


async def llm(
    prompt: str, *, as_json: bool = False, max_tokens: int = 500, temperature: float = 0.1, fast: bool = False
) -> str | dict:
    from features.brain.llm import generate

    return await generate(prompt, as_json=as_json, max_tokens=max_tokens, temperature=temperature,
                          kind="chat" if fast else "deep")


def note_gap(text: str, reason: str) -> None:
    try:
        gaps = json.loads(GAPS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        gaps = []
    gaps.append({"text": text[:300], "reason": reason[:300], "at": time.time()})
    GAPS_FILE.write_text(json.dumps(gaps[-200:], ensure_ascii=False, indent=1), encoding="utf-8")


def fmt_num(v: float, decimals: int | None = None) -> str:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return str(v)
    if v != v or v in (float("inf"), float("-inf")):
        return "indefinito"
    if decimals is not None:
        s = f"{v:,.{decimals}f}"
    elif float(v).is_integer() and abs(v) < 1e15:
        s = f"{int(v):,}"
    elif abs(v) >= 1e15 or abs(v) < 1e-6:
        return f"{v:.6g}".replace(".", ",")
    else:
        s = f"{v:,.6f}".rstrip("0").rstrip(".")
    return s.replace(",", " ").replace(".", ",").replace(" ", ".")


def human_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}".replace(".", ",")
        n /= 1024
    return str(n)
