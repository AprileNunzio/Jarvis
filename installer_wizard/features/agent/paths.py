from pathlib import Path

from config import DEMO, STATE_DIR, env_get

from features.actions.common import WORK_DIR
from features.shares import archive

WORK = (STATE_DIR / "srv") if DEMO else WORK_DIR
FILES = archive.path("documenti")
TRASH = STATE_DIR / "cestino"
MODELS = STATE_DIR / "models3d"
FORBIDDEN = ("/proc", "/sys", "/dev", "/boot", "/etc/shadow", "/etc/gshadow", "/etc/sudoers")


class AccessDenied(Exception):
    pass


def level() -> str:
    value = env_get("JARVIS_AGENT_ACCESS", "completo").lower()
    return value if value in ("standard", "completo") else "completo"


def roots() -> list[Path]:
    return [WORK, MODELS]


def inside(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def resolve(raw: str) -> Path:
    text = str(raw or "").strip().strip("\"'")
    if not text:
        raise ValueError("percorso mancante")
    p = Path(text).expanduser()
    if not p.is_absolute():
        p = FILES / p
    p = p.resolve()
    if any(str(p).startswith(f) for f in FORBIDDEN):
        raise AccessDenied(f"{p} è un'area protetta del sistema")
    if level() == "standard" and not any(inside(p, r) for r in roots()):
        raise AccessDenied(f"con l'accesso standard posso lavorare solo in {WORK} e nei modelli 3D")
    return p


def trusted(path: Path) -> bool:
    return any(inside(path, r) for r in roots())
