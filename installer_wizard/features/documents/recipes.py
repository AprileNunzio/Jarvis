import json
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

from config import STATE_DIR
from state import store

from features.documents import convert

FILE = STATE_DIR / "conversion_recipes.json"
EXPORT = {("docx", "pdf"): "pdf:writer_pdf_Export", ("odt", "pdf"): "pdf:writer_pdf_Export",
          ("xlsx", "pdf"): "pdf:calc_pdf_Export", ("ods", "pdf"): "pdf:calc_pdf_Export",
          ("pptx", "pdf"): "pdf:impress_pdf_Export", ("odp", "pdf"): "pdf:impress_pdf_Export",
          ("docx", "odt"): "odt:writer8", ("xlsx", "ods"): "ods:calc8", ("pptx", "odp"): "odp:impress8"}
VIA = {"docx": "odt", "xlsx": "ods", "pptx": "odp"}
MIME = {"odt": "application/vnd.oasis.opendocument.text", "ods": "application/vnd.oasis.opendocument.spreadsheet",
        "odp": "application/vnd.oasis.opendocument.presentation"}


def load() -> dict:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(data: dict) -> None:
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def valid(path: Path, ext: str) -> bool:
    try:
        if ext == "pdf":
            with path.open("rb") as fh:
                return fh.read(5) == b"%PDF-" and path.stat().st_size > 800
        if ext in MIME:
            with zipfile.ZipFile(path) as z:
                return z.read("mimetype").decode().strip() == MIME[ext]
        return zipfile.is_zipfile(path)
    except (OSError, KeyError, zipfile.BadZipFile):
        return False


def candidates(src: str, dst: str) -> list[list[dict]]:
    routes = [[{"to": dst, "filter": dst}]]
    if (src, dst) in EXPORT:
        routes.append([{"to": dst, "filter": EXPORT[(src, dst)]}])
    if src in VIA and VIA[src] != dst:
        mid = VIA[src]
        routes.append([{"to": mid, "filter": EXPORT.get((src, mid), mid)}, {"to": dst, "filter": EXPORT.get((mid, dst), dst)}])
    return routes


async def _run(route: list[dict], source: Path, work: Path) -> Path:
    current = source
    for step in route:
        current = await convert.convert(current, step["to"], work, step["filter"])
    return current


async def transform(source: Path, dst: str, out_dir: Path) -> tuple[Path, str]:
    src = source.suffix.lower().lstrip(".")
    key = f"{src}>{dst}"
    data = load()
    known = data.get(key)
    routes = ([known["route"]] if known else []) + [r for r in candidates(src, dst) if not known or r != known["route"]]
    errors = []
    for i, route in enumerate(routes):
        started = time.time()
        with tempfile.TemporaryDirectory(prefix="jarvis-recipe-") as tmp:
            try:
                produced = await _run(route, source, Path(tmp))
            except RuntimeError as exc:
                errors.append(str(exc)[:120])
                continue
            if not valid(produced, dst):
                errors.append(f"risultato non valido con {route}")
                continue
            target = out_dir / f"{source.stem}.{dst}"
            shutil.move(str(produced), target)
        seconds = time.time() - started
        learned = not known or i > 0
        entry = data.get(key) if not learned else {"route": route, "learned": time.time(), "uses": 0, "avg_s": seconds}
        entry["uses"] = entry.get("uses", 0) + 1
        entry["avg_s"] = round(entry.get("avg_s", seconds) * 0.7 + seconds * 0.3, 2)
        entry["last_ok"] = time.time()
        data[key] = entry
        save(data)
        if learned:
            store.event("INFO", f"Ho imparato a convertire {src.upper()} in {dst.upper()} e ho salvato la procedura", "documents")
        return target, "appresa ora" if learned else "dalla memoria"
    if known:
        data.pop(key, None)
        save(data)
    raise RuntimeError(f"nessuna procedura riesce a convertire {src.upper()} in {dst.upper()}: " + "; ".join(errors[-3:]))


def overview() -> list[dict]:
    return [{"conversion": k.replace(">", " → ").upper(), "steps": " → ".join(s["to"].upper() for s in v["route"]),
             "uses": v.get("uses", 0), "avg_s": v.get("avg_s"), "learned": v.get("learned"), "last_ok": v.get("last_ok")}
            for k, v in sorted(load().items())]
