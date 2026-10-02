import shutil
import time
import zipfile
from pathlib import Path

from features.agent.paths import FILES, TRASH, resolve, trusted
from features.agent.registry import tool
from features.shares import archive

TEXT_LIMIT = 8000


def _size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _write_risk(args: dict) -> bool:
    return not trusted(resolve(args.get("path", "")))


@tool("list_dir", "elenca il contenuto di una cartella (vuoto = cartella di lavoro)", {"path": "cartella"})
async def list_dir(path: str = "") -> str:
    p = resolve(path or str(FILES))
    if not p.is_dir():
        return f"{p} non è una cartella"
    items = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))[:200]
    rows = [f"{'📁' if i.is_dir() else '📄'} {i.name}{'' if i.is_dir() else ' (' + _size(i.stat().st_size) + ')'}" for i in items]
    return f"{p}:\n" + ("\n".join(rows) or "(vuota)")


@tool("read_file", "legge un file di testo", {"path": "file"})
async def read_file(path: str) -> str:
    p = resolve(path)
    data = p.read_text(encoding="utf-8", errors="replace")
    return data[:TEXT_LIMIT] + ("\n…(troncato)" if len(data) > TEXT_LIMIT else "")


@tool("write_file", "crea o sovrascrive un file di testo (append=true per aggiungere in fondo)",
      {"path": "file", "content": "testo", "append": "true/false"}, confirm=_write_risk)
async def write_file(path: str, content: str, append: bool = False) -> str:
    p = resolve(path)
    if not p.exists() and p.parent.parent == archive.ROOT and not archive.DATED.match(p.name):
        p = archive.unique(p.parent, archive.dated(p.name))
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a" if str(append).lower() == "true" else "w", encoding="utf-8") as f:
        f.write(str(content))
    return f"scritto {p} ({_size(p.stat().st_size)})"


@tool("make_dir", "crea una cartella (anche annidata)", {"path": "cartella"}, confirm=_write_risk)
async def make_dir(path: str) -> str:
    p = resolve(path)
    p.mkdir(parents=True, exist_ok=True)
    return f"cartella pronta: {p}"


@tool("copy", "copia un file o una cartella", {"src": "origine", "dst": "destinazione"},
      confirm=lambda a: not trusted(resolve(a.get("dst", ""))))
async def copy(src: str, dst: str) -> str:
    s, d = resolve(src), resolve(dst)
    if d.is_dir():
        d = d / s.name
    d.parent.mkdir(parents=True, exist_ok=True)
    if s.is_dir():
        shutil.copytree(s, d, dirs_exist_ok=True)
    else:
        shutil.copy2(s, d)
    return f"copiato in {d}"


@tool("move", "sposta o rinomina un file o una cartella", {"src": "origine", "dst": "destinazione"},
      confirm=lambda a: not (trusted(resolve(a.get("src", ""))) and trusted(resolve(a.get("dst", "")))))
async def move(src: str, dst: str) -> str:
    s, d = resolve(src), resolve(dst)
    if d.is_dir():
        d = d / s.name
    d.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(s), str(d))
    return f"spostato in {d}"


@tool("delete", "sposta un file o una cartella nel cestino di Jarvis (recuperabile)", {"path": "percorso"}, confirm=True)
async def delete(path: str) -> str:
    p = resolve(path)
    if not p.exists():
        return f"{p} non esiste"
    dest = TRASH / time.strftime("%Y%m%d-%H%M%S") / p.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(p), str(dest))
    return f"spostato nel cestino: {dest}"


@tool("zip", "comprime un file o una cartella in un archivio .zip", {"path": "percorso", "dst": "archivio .zip (facoltativo)"})
async def zip_path(path: str, dst: str = "") -> str:
    p = resolve(path)
    out = resolve(dst) if dst else p.with_suffix(".zip") if p.is_file() else p.parent / f"{p.name}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in ([p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file())):
            z.write(f, f.name if p.is_file() else f.relative_to(p.parent))
    return f"archivio creato: {out} ({_size(out.stat().st_size)})"


@tool("find_files", "cerca file per nome (es. *.stl) in una cartella", {"pattern": "schema", "root": "cartella (facoltativa)"})
async def find_files(pattern: str, root: str = "") -> str:
    base = resolve(root or str(FILES))
    found = [str(x) for _, x in zip(range(100), base.rglob(pattern or "*"))]
    return "\n".join(found) or "nessun file trovato"


@tool("file_info", "dimensione e data di un file", {"path": "percorso"})
async def file_info(path: str) -> str:
    p: Path = resolve(path)
    st = p.stat()
    return f"{p}: {_size(st.st_size)}, modificato il {time.strftime('%d/%m/%Y %H:%M', time.localtime(st.st_mtime))}"
