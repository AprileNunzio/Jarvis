import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

BLOCK_TYPES = ("text", "list", "steps", "table", "image", "code", "kv", "quote", "model3d")
MAX_BLOCKS = 6
MAX_IMAGES = 2
MAX_ITEMS = 12
MAX_TABLE_ROWS = 20
MAX_TABLE_COLUMNS = 6
MIN_SPAN = 3
FULL_ROW = 12
_TEXT_LIMIT = 1800
_CODE_LIMIT = 6000
_TITLE_LIMIT = 80
_SPEECH_LIMIT = 420
_DEFAULT_SPAN = {"text": 12, "list": 12, "steps": 12, "table": 12, "image": 6, "code": 12, "kv": 6, "quote": 12}
_LANGUAGE = re.compile(r"^[a-z0-9+#.-]{1,20}$")


class PlanError(ValueError):
    pass


@dataclass(frozen=True)
class Block:
    type: str
    span: int
    title: str = ""
    fields: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Plan:
    mode: str
    title: str
    subtitle: str
    speech: str
    blocks: Tuple[Block, ...]


def _text(value: Any, limit: int, multiline: bool = False) -> str:
    raw = str(value or "")
    return raw.strip()[:limit] if multiline else " ".join(raw.split())[:limit]


def _strings(value: Any, limit: int = MAX_ITEMS, size: int = 240) -> List[str]:
    if not isinstance(value, (list, tuple)):
        raise PlanError("a list of strings was expected")
    items = [" ".join(str(v).split())[:size] for v in value if str(v).strip()]
    return items[:limit]


def _span(raw: Mapping[str, Any], kind: str) -> int:
    try:
        span = int(raw.get("span", _DEFAULT_SPAN.get(kind, FULL_ROW)))
    except (TypeError, ValueError):
        raise PlanError("span must be a number")
    return max(MIN_SPAN, min(FULL_ROW, span))


def _text_fields(raw: Mapping[str, Any]) -> Dict[str, Any]:
    body = _text(raw.get("body"), _TEXT_LIMIT, multiline=True)
    if len(body) < 2:
        raise PlanError("text block without body")
    return {"body": body}


def _list_fields(raw: Mapping[str, Any]) -> Dict[str, Any]:
    items = _strings(raw.get("items"))
    if not items:
        raise PlanError("list block without items")
    return {"items": items}


def _table_fields(raw: Mapping[str, Any]) -> Dict[str, Any]:
    columns = _strings(raw.get("columns"), MAX_TABLE_COLUMNS, 60)
    rows = raw.get("rows")
    if not columns or not isinstance(rows, (list, tuple)):
        raise PlanError("table block needs columns and rows")
    clean = []
    for row in rows[:MAX_TABLE_ROWS]:
        if not isinstance(row, (list, tuple)):
            raise PlanError("table rows must be lists")
        cells = [" ".join(str(c).split())[:120] for c in row][: len(columns)]
        clean.append(cells + [""] * (len(columns) - len(cells)))
    if not clean:
        raise PlanError("table block without rows")
    return {"columns": columns, "rows": clean}


def _image_fields(raw: Mapping[str, Any]) -> Dict[str, Any]:
    query = _text(raw.get("query"), 80)
    if len(query) < 2:
        raise PlanError("image block without query")
    return {"query": query, "caption": _text(raw.get("caption"), 140), "cutout": bool(raw.get("cutout"))}


def _code_fields(raw: Mapping[str, Any]) -> Dict[str, Any]:
    content = str(raw.get("content") or "").strip("\n")[:_CODE_LIMIT]
    language = str(raw.get("language") or "testo").strip().lower()
    if not content.strip():
        raise PlanError("code block without content")
    return {"content": content, "language": language if _LANGUAGE.match(language) else "testo"}


def _kv_fields(raw: Mapping[str, Any]) -> Dict[str, Any]:
    items = raw.get("items")
    if not isinstance(items, (list, tuple)):
        raise PlanError("kv block needs items")
    pairs = {}
    for item in items[:MAX_ITEMS]:
        if isinstance(item, Mapping) and str(item.get("k", "")).strip():
            pairs[_text(item["k"], 60)] = _text(item.get("v"), 160)
    if not pairs:
        raise PlanError("kv block without pairs")
    return {"pairs": pairs}


def _quote_fields(raw: Mapping[str, Any]) -> Dict[str, Any]:
    body = _text(raw.get("body"), 400)
    if len(body) < 2:
        raise PlanError("quote block without body")
    return {"body": body, "source": _text(raw.get("source"), 80)}


def _model_fields(raw: Mapping[str, Any]) -> Dict[str, Any]:
    subject = _text(raw.get("subject"), 60)
    if len(subject) < 2:
        raise PlanError("model3d block without subject")
    return {"subject": subject}


_BUILDERS = {
    "text": _text_fields, "list": _list_fields, "steps": _list_fields, "table": _table_fields, "image": _image_fields,
    "code": _code_fields, "kv": _kv_fields, "quote": _quote_fields, "model3d": _model_fields,
}


def parse_block(raw: Any) -> Block:
    if not isinstance(raw, Mapping):
        raise PlanError("a block must be an object")
    kind = str(raw.get("type") or "").strip().lower()
    if kind not in _BUILDERS:
        raise PlanError(f"unknown block type: {kind or '(missing)'}")
    return Block(kind, _span(raw, kind), _text(raw.get("title"), _TITLE_LIMIT), _BUILDERS[kind](raw))


def parse_plan(raw: Any, fallback_speech: str = "") -> Plan:
    if not isinstance(raw, Mapping):
        raise PlanError("the plan must be an object")
    mode = str(raw.get("mode") or "focus").strip().lower()
    if mode not in ("focus", "face"):
        raise PlanError("mode must be focus or face")
    speech = _text(raw.get("speech"), _SPEECH_LIMIT) or fallback_speech[:_SPEECH_LIMIT]
    if not speech:
        raise PlanError("the plan needs a speech")
    if mode == "face":
        return Plan("face", "", "", speech, ())
    items = raw.get("blocks")
    if not isinstance(items, (list, tuple)) or not items:
        raise PlanError("the plan needs at least one block")
    blocks = [parse_block(item) for item in items[:MAX_BLOCKS]]
    if sum(b.type == "image" for b in blocks) > MAX_IMAGES:
        raise PlanError(f"at most {MAX_IMAGES} images")
    if sum(b.type == "model3d" for b in blocks) > 1:
        raise PlanError("at most one 3D model")
    if not any(b.type != "model3d" for b in blocks):
        raise PlanError("the plan needs at least one visible block")
    return Plan("focus", _text(raw.get("title"), _TITLE_LIMIT) or "Jarvis", _text(raw.get("subtitle"), 120), speech, tuple(blocks))


def fill_rows(blocks: List[Block]) -> List[Block]:
    rows: List[List[Block]] = []
    used = 0
    for block in blocks:
        if rows and used + block.span <= FULL_ROW:
            rows[-1].append(block)
            used += block.span
        else:
            rows.append([block])
            used = block.span
    out: List[Block] = []
    for row in rows:
        spare = FULL_ROW - sum(b.span for b in row)
        for index, block in enumerate(row):
            extra = spare if index == len(row) - 1 else 0
            out.append(Block(block.type, min(FULL_ROW, block.span + extra), block.title, block.fields))
    return out


def side_effects(plan: Plan) -> Optional[str]:
    return next((str(b.fields["subject"]) for b in plan.blocks if b.type == "model3d"), None)
