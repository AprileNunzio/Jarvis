import re
import time
import unicodedata
from pathlib import Path

from config import DEMO, STATE_DIR

SHARE = "condivisa"
ROOT = (STATE_DIR / "srv" / SHARE) if DEMO else Path("/srv/jarvis") / SHARE
FOLDERS = {
    "documenti": "01 Documenti",
    "siti": "02 Siti web",
    "modelli3d": "03 Modelli 3D",
    "codice": "04 Codice",
    "scambio": "05 Scambio",
}
DESCRIPTIONS = {
    "documenti": "testi, note, elenchi e documenti scritti da Jarvis",
    "siti": "siti web creati da Jarvis, uno per cartella, visibili anche dal browser",
    "modelli3d": "oggetti 3D progettati da Jarvis (GLB, STL per la stampa, OBJ)",
    "codice": "il codice mostrato da Jarvis sullo schermo, pronto da riusare",
    "scambio": "cartella libera per scambiare file con Jarvis e sottocartelle create a richiesta",
}
README = "LEGGIMI.txt"
DATED = re.compile(r"^\d{8}_")
UNSAFE = re.compile(r"[^A-Za-z0-9._ -]+")


def path(kind: str) -> Path:
    return ROOT / FOLDERS[kind]


def folder(kind: str) -> Path:
    target = path(kind)
    target.mkdir(parents=True, exist_ok=True)
    return target


def stamp() -> str:
    return time.strftime("%Y%m%d")


def clean(name: str, fallback: str = "file") -> str:
    plain = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode()
    plain = UNSAFE.sub(" ", plain)
    plain = re.sub(r"\s+", "-", plain.strip()).strip(".-_")
    return plain[:80] or fallback


def dated(name: str, fallback: str = "file") -> str:
    raw = Path(str(name or "")).name
    suffix = Path(raw).suffix.lower() if Path(raw).suffix and len(Path(raw).suffix) <= 8 else ""
    stem = clean(raw[: -len(suffix)] if suffix else raw, fallback)
    return f"{stem}{suffix}" if DATED.match(stem) else f"{stamp()}_{stem}{suffix}"


def unique(directory: Path, name: str) -> Path:
    candidate = directory / name
    stem, suffix = Path(name).stem, Path(name).suffix
    n = 2
    while candidate.exists():
        candidate = directory / f"{stem}_{n}{suffix}"
        n += 1
    return candidate


def new_path(kind: str, name: str, fallback: str = "file") -> Path:
    return unique(folder(kind), dated(name, fallback))


def unc(ip: str, kind: str = "") -> str:
    base = f"\\\\{ip}\\{SHARE}"
    return f"{base}\\{FOLDERS[kind]}" if kind else base


def readme() -> str:
    lines = ["Cartella condivisa di Jarvis", "", "Qui Jarvis salva tutto ciò che crea, in queste sottocartelle:", ""]
    lines += [f"  {FOLDERS[k]:<16} {DESCRIPTIONS[k]}" for k in FOLDERS]
    lines += ["", "La memoria di Jarvis (persone, fatti, diario) non è qui: per privacy resta solo sul server.",
              "", "I nomi iniziano sempre con la data in ordine inverso (AAAAMMGG_nome), così l'ordine alfabetico",
              "è anche quello cronologico: per esempio 20261002_lista-della-spesa.txt.",
              "", "L'accesso richiede l'utente jarvis-share e la password indicata nel pannello di Jarvis",
              "(Condivisioni di rete)."]
    return "\n".join(lines) + "\n"


def ensure() -> Path:
    for kind in FOLDERS:
        folder(kind)
    note = ROOT / README
    text = readme()
    try:
        if not note.exists() or note.read_text(encoding="utf-8") != text:
            note.write_text(text, encoding="utf-8")
    except OSError:
        pass
    return ROOT


def overview() -> list[dict]:
    rows = []
    for kind, name in FOLDERS.items():
        target = path(kind)
        items = sorted((p for p in target.iterdir() if not p.name.startswith(".")), reverse=True) if target.exists() else []
        rows.append({"kind": kind, "name": name, "description": DESCRIPTIONS[kind], "count": len(items),
                     "latest": [p.name for p in items[:3]]})
    return rows
