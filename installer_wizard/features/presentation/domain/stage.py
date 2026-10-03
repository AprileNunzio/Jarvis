from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from features.presentation.domain.plan import Block, Plan, fill_rows


@dataclass(frozen=True)
class ImageAsset:
    src: str
    credit: str = ""
    license: str = ""
    page: str = ""


def _panel(block: Block, image: Optional[ImageAsset]) -> Optional[Dict[str, Any]]:
    fields = block.fields
    base: Dict[str, Any] = {"type": block.type, "span": block.span}
    if block.title:
        base["title"] = block.title
    if block.type == "text":
        return {**base, "body": fields["body"]}
    if block.type == "list":
        return {**base, "items": [{"label": item, "value": "", "status": ""} for item in fields["items"]]}
    if block.type == "steps":
        return {**base, "items": list(fields["items"])}
    if block.type == "table":
        return {**base, "columns": list(fields["columns"]), "rows": [list(r) for r in fields["rows"]]}
    if block.type == "code":
        return {**base, "language": fields["language"], "content": fields["content"]}
    if block.type == "kv":
        return {**base, "type": "kv", "data": dict(fields["pairs"])}
    if block.type == "quote":
        return {**base, "body": fields["body"], "source": fields["source"]}
    if block.type == "image":
        if image is None:
            return None
        credit = " · ".join(part for part in (image.credit, image.license) if part)
        return {**base, "src": image.src, "caption": fields.get("caption", ""), "credit": credit, "page": image.page}
    return None


def to_ui(plan: Plan, images: Mapping[int, ImageAsset]) -> Dict[str, Any]:
    if plan.mode == "face":
        return {"mode": "face"}
    kept: List[Block] = []
    panels: Dict[int, Dict[str, Any]] = {}
    for index, block in enumerate(plan.blocks):
        panel = _panel(block, images.get(index))
        if panel is not None:
            kept.append(block)
            panels[len(kept) - 1] = panel
    if not kept:
        return {"mode": "face"}
    spans = [b.span for b in fill_rows(kept)]
    ordered = [{**panels[i], "span": spans[i]} for i in range(len(kept))]
    return {"mode": "focus", "layout": "grid", "title": plan.title, "subtitle": plan.subtitle or "Impaginato da Jarvis",
            "panels": ordered}
