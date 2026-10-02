import re
import shutil
import tempfile
from pathlib import Path

from features.documents import excel, recipes, slides, spec, word

FORMAT_WORDS = [
    ("pdf", r"\bpdf\b"),
    ("odt", r"\b(odt|writer)\b|\b(libre|open)\s*office\b[^.?!]{0,40}\b(document\w*|lettera|relazione|testo)\b"),
    ("ods", r"\b(ods|calc)\b|\b(libre|open)\s*office\b[^.?!]{0,40}\b(fogli\w*|tabell\w*|calcolo)\b"),
    ("odp", r"\b(odp|impress)\b|\b(libre|open)\s*office\b[^.?!]{0,40}\b(presentazion\w*|slide|diapositiv\w*)\b"),
    ("xlsx", r"\b(excel|xlsx|fogli\w*\s+(di\s+)?(calcolo|elettronic\w*|excel)|spreadsheet|tabell\w*\s+excel|budget|bilancio)\b"),
    ("pptx", r"\b(power\s*point|pptx|presentazion\w*|slide|diapositiv\w*|pitch)\b"),
    ("docx", r"\b(word|docx|document\w*|relazion\w*|lettera|curriculum|cv|contratto|verbale|report|manuale|guida|"
             r"proposta|offerta|preventivo|brochure|volantino|articolo|tesina|piano|business\s+plan|lettera)\b"),
]
RENDER = {"documento": word.write, "foglio": excel.write, "presentazione": slides.write}


def formats(text: str) -> list[str]:
    found = [fmt for fmt, pattern in FORMAT_WORDS if re.search(pattern, text, re.I)]
    if "pdf" in found and len(found) > 1 and "docx" in found and not re.search(r"\b(word|docx)\b", text, re.I):
        found.remove("docx")
    odf = {"docx": ("odt", r"word|docx"), "xlsx": ("ods", r"excel|xlsx"), "pptx": ("odp", r"power\s*point|pptx")}
    if re.search(r"\b(libre|open)\s*office\b", text, re.I):
        found = [odf[f][0] if f in odf and not re.search(rf"\b({odf[f][1]})\b", text, re.I) else f for f in found]
    for base, (o, explicit) in odf.items():
        if o in found and base in found and not re.search(rf"\b({explicit})\b", text, re.I):
            found.remove(base)
    return list(dict.fromkeys(found)) or ["docx"]


async def design(kind: str, request: str, context: str = "") -> dict:
    from features.documents import planner
    return await planner.design(kind, request, context)


def kind_of(fmts: list[str]) -> str:
    return next((spec.KINDS[f] for f in fmts if f != "pdf"), "documento")


async def render(doc: dict, fmt: str, target: Path, links: dict | None = None) -> Path:
    kind = doc.get("kind") or spec.KINDS[fmt]
    base = spec.BASE_FORMAT[kind]
    if fmt == base:
        return RENDER[kind](doc, target, links)
    with tempfile.TemporaryDirectory(prefix="jarvis-doc-") as tmp:
        source = Path(tmp) / f"{target.stem}.{base}"
        RENDER[kind](doc, source, links)
        produced, _ = await recipes.transform(source, fmt, Path(tmp))
        shutil.move(str(produced), target)
    return target


def describe(doc: dict) -> str:
    if doc["kind"] == "documento":
        heads = sum(1 for b in doc["blocks"] if b["type"] == "heading")
        tables = sum(1 for b in doc["blocks"] if b["type"] == "table")
        graphs = sum(1 for b in doc["blocks"] if b["type"] == "chart")
        return f"{heads} sezioni, {tables} tabelle, {graphs} grafici"
    if doc["kind"] == "foglio":
        rows = sum(len(s["rows"]) for s in doc["sheets"])
        graphs = sum(1 for s in doc["sheets"] if s.get("chart"))
        return f"{len(doc['sheets'])} fogli, {rows} righe, {graphs} grafici"
    graphs = sum(1 for s in doc["slides"] if s.get("chart"))
    return f"{len(doc['slides'])} diapositive, {graphs} grafici"
