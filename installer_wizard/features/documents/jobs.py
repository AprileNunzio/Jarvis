import asyncio
import importlib
import importlib.util
import json
import os
import re
import time
import uuid
from pathlib import Path

from config import STATE_DIR
from state import store

from features.documents import builder, convert, recipes, spec, word
from features.shares import archive

INDEX = STATE_DIR / "documents.json"
PREVIEWS = STATE_DIR / "documents-previews"
PROJECT = re.compile(r"\b(progett\w*|pacchetto|kit|dossier|cartella\s+(di|del|con|per)|più\s+documenti|diversi\s+documenti|"
                     r"tutti\s+i\s+documenti|set\s+di\s+documenti|documentazione\s+complet\w*)\b", re.I)
PARALLEL = 3
MAX_DOCS = 12
PLAN = (
    "Sei un consulente che organizza un progetto documentale professionale. Pianifica cartelle e documenti per la "
    "richiesta. Rispondi SOLO con JSON:\n"
    '{"project": "nome del progetto", "description": "2-3 frasi", "theme": "moderno|aziendale|elegante|vivace|minimal|'
    'natura|tech", "folders": ["01 Analisi", "02 Finanza"], "documents": [{"key": "budget", "title": "Budget 2027", '
    '"folder": "02 Finanza", "format": "docx|xlsx|pptx|odt|ods|odp|pdf", "brief": "contenuto dettagliato", '
    '"links": ["chiavi di altri documenti collegati"]}]}\n'
    "Da 2 a 10 documenti, formati adatti al contenuto (numeri e calcoli in fogli di calcolo, sintesi in "
    "presentazione, testi in documenti), cartelle numerate per fase.\n\nRichiesta: "
)


def load() -> dict:
    try:
        return json.loads(INDEX.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def remember(entry: dict) -> None:
    data = load()
    data[entry["id"]] = entry
    for old in sorted(data, key=lambda k: data[k].get("created", 0))[:-200]:
        data.pop(old, None)
    INDEX.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def rel(path: Path) -> str:
    return path.relative_to(archive.ROOT).as_posix()


def link_to(source_dir: Path, target: Path) -> str:
    return Path(os.path.relpath(target, source_dir)).as_posix()


async def preview(entry_id: str, source: Path) -> str:
    if not convert.office():
        return ""
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    try:
        if source.suffix == ".pdf":
            target = PREVIEWS / f"{entry_id}.pdf"
            target.write_bytes(source.read_bytes())
            return target.name
        made, _ = await recipes.transform(source, "pdf", PREVIEWS)
        target = PREVIEWS / f"{entry_id}.pdf"
        made.replace(target)
        return target.name
    except (RuntimeError, OSError):
        return ""


def wants_project(text: str) -> bool:
    kinds = {spec.KINDS[f] for f in builder.formats(text) if f != "pdf"}
    return bool(PROJECT.search(text)) or len(kinds) > 1


async def single(request: str) -> dict:
    fmts = builder.formats(request)
    kind = builder.kind_of(fmts)
    if "pdf" in fmts and spec.BASE_FORMAT[kind] not in fmts and not any(f in fmts for f in ("odt", "ods", "odp")):
        fmts = ["pdf", spec.BASE_FORMAT[kind]] + [f for f in fmts if f != "pdf"]
    doc = await builder.design(kind, request)
    folder = archive.folder("documenti")
    name = archive.dated(archive.clean(doc["title"], "documento"))
    files = []
    for fmt in [f for f in fmts if f == "pdf" or spec.KINDS[f] == kind] or [spec.BASE_FORMAT[kind]]:
        target = archive.unique(folder, f"{name}.{fmt}")
        files.append(await builder.render(doc, fmt, target))
    entry = {"id": uuid.uuid4().hex[:10], "title": doc["title"], "kind": kind, "created": time.time(), "request": request[:300],
             "files": [rel(f) for f in files], "summary": builder.describe(doc), "project": ""}
    entry["preview"] = await preview(entry["id"], files[0])
    remember(entry)
    return entry


def _project_paths(plan: dict, root: Path) -> list[dict]:
    docs, used = [], set()
    for d in (plan.get("documents") or [])[:MAX_DOCS]:
        if not isinstance(d, dict) or not d.get("title"):
            continue
        fmt = str(d.get("format") or "docx").lower().strip(".")
        fmt = fmt if fmt in spec.KINDS else "docx"
        key = archive.clean(str(d.get("key") or d["title"]), "doc").lower()
        while key in used:
            key += "-2"
        used.add(key)
        folder = root / archive.clean(str(d.get("folder") or ""), "") if d.get("folder") else root
        folder.mkdir(parents=True, exist_ok=True)
        target = archive.unique(folder, f"{archive.dated(archive.clean(str(d['title']), 'documento'))}.{fmt}")
        docs.append({"key": key, "title": spec.text(d["title"], 120), "format": fmt, "brief": spec.text(d.get("brief"), 1200),
                     "path": target, "links": [archive.clean(str(x), "").lower() for x in (d.get("links") or [])]})
    return docs


async def project(request: str) -> dict:
    from features.brain.llm import generate
    plan = await generate(PLAN + request, as_json=True, max_tokens=2500, temperature=0.3, kind="deep", timeout=600)
    plan = plan if isinstance(plan, dict) else {}
    title = spec.text(plan.get("project"), 100) or spec.text(request, 60)
    root = archive.new_path("documenti", archive.clean(title, "progetto"), "progetto")
    root.mkdir(parents=True, exist_ok=True)
    for f in (plan.get("folders") or [])[:12]:
        (root / archive.clean(str(f), "cartella")).mkdir(exist_ok=True)
    docs = _project_paths(plan, root)
    if not docs:
        raise ValueError("il piano del progetto non contiene documenti")
    context = (f"Progetto «{title}»: {spec.text(plan.get('description'), 600)}\nDocumenti del progetto (chiave: titolo, formato, "
               "contenuto). Per rimandare a un altro documento usa un blocco/collegamento link con target uguale alla chiave:\n" +
               "\n".join(f"- {d['key']}: {d['title']} ({d['format']}) — {d['brief'][:200]}" for d in docs))
    theme = spec.text(plan.get("theme"), 20)
    slots = asyncio.Semaphore(PARALLEL)
    errors = []

    async def build(d: dict) -> None:
        kind = spec.KINDS[d["format"]]
        links = {o["key"]: link_to(d["path"].parent, o["path"]) for o in docs if o is not d}
        async with slots:
            try:
                doc = await builder.design(kind, f"{d['title']}: {d['brief']}", context)
                doc["theme"] = doc.get("theme") or theme
                if kind == "documento" and d["links"]:
                    doc["blocks"] += [{"type": "heading", "level": 2, "text": "Documenti collegati"}] + [
                        {"type": "link", "text": next((o["title"] for o in docs if o["key"] == k), k), "target": k}
                        for k in d["links"] if k in links]
                if kind == "foglio" and d["links"]:
                    doc["sheets"][0]["links"] += [{"text": next((o["title"] for o in docs if o["key"] == k), k), "target": k}
                                                  for k in d["links"] if k in links]
                await builder.render(doc, d["format"], d["path"], links)
                d["summary"] = builder.describe(doc)
            except Exception as exc:
                errors.append(f"{d['title']}: {str(exc)[:120]}")
                d["failed"] = True

    await asyncio.gather(*(build(d) for d in docs))
    made = [d for d in docs if not d.get("failed")]
    index_path = root / f"{archive.stamp()}_00_Indice-del-progetto.docx"
    index = {"kind": "documento", "title": title, "subtitle": spec.text(plan.get("description"), 300), "author": "Jarvis",
             "theme": theme, "palette": [], "font": "", "blocks": [
                 {"type": "heading", "level": 1, "text": "Panoramica"},
                 {"type": "paragraph", "text": spec.text(plan.get("description"), 1200) or request, "align": "justify"},
                 {"type": "heading", "level": 1, "text": "Documenti del progetto"},
                 {"type": "table", "columns": ["Documento", "Cartella", "Formato", "Contenuto"], "caption": "", "totals": False,
                  "rows": [[d["title"], d["path"].parent.name if d["path"].parent != root else "—", d["format"].upper(),
                            d.get("summary", "")] for d in made]},
                 {"type": "heading", "level": 2, "text": "Apri i documenti"}] +
             [{"type": "link", "text": f"{d['title']} ({d['format'].upper()})", "target": d["key"]} for d in made]}
    word.write(index, index_path, {d["key"]: link_to(root, d["path"]) for d in made})
    entry = {"id": uuid.uuid4().hex[:10], "title": title, "kind": "progetto", "created": time.time(), "request": request[:300],
             "project": rel(root), "files": [rel(index_path)] + [rel(d["path"]) for d in made],
             "summary": f"{len(made)} documenti in {len({d['path'].parent for d in made})} cartelle", "errors": errors}
    entry["preview"] = await preview(entry["id"], index_path)
    remember(entry)
    return entry


LIBRARIES = {"docx": "python-docx", "openpyxl": "openpyxl", "pptx": "python-pptx", "matplotlib": "matplotlib"}


def missing(fmts: list[str]) -> list[str]:
    importlib.invalidate_caches()
    out = [name for module, name in LIBRARIES.items() if importlib.util.find_spec(module) is None]
    if any(f in ("odt", "ods", "odp", "pdf") for f in fmts) and not convert.office():
        out.append("LibreOffice")
    return out


async def prepare(fmts: list[str]) -> None:
    if not missing(fmts):
        return
    from orchestrator import orch
    await orch.ensure(["office"], "servono per preparare i documenti")
    still = missing(fmts)
    if still:
        raise RuntimeError("non sono riuscito a installare " + ", ".join(still))


async def run(request: str) -> dict:
    started = time.time()
    await prepare(["pdf"] if wants_project(request) else builder.formats(request))
    entry = await (project(request) if wants_project(request) else single(request))
    entry["seconds"] = round(time.time() - started)
    store.event("INFO", f"Documenti creati: {entry['title']} ({entry['summary']})", "documents")
    return entry
