import json
import time

from config import STATE_DIR

TEMPLATES_FILE = STATE_DIR / "ui_templates.json"
NEVER_PREDICT = {"conversation", "code_view", "laws", "action", "agent"}
STABLE_USES = 3


def load_templates() -> dict:
    try:
        return json.loads(TEMPLATES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_templates(data: dict) -> None:
    tmp = TEMPLATES_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(TEMPLATES_FILE)


def remember_template(intent: str, ui: dict, elapsed_ms: int) -> None:
    templates = load_templates()
    skeleton = {"mode": ui.get("mode"), "panels": [{"type": p["type"], "title": p.get("title", "")}
                                                    for p in ui.get("panels", [])]}
    tpl = templates.get(intent, {"uses": 0, "avg_ms": elapsed_ms, "score": None, "reviews": 0})
    tpl["stable"] = tpl.get("stable", 0) + 1 if tpl.get("skeleton") == skeleton else 1
    tpl.update(skeleton=skeleton, last_used=time.time(), uses=tpl["uses"] + 1,
               avg_ms=int(tpl["avg_ms"] * 0.7 + elapsed_ms * 0.3))
    templates[intent] = tpl
    _save_templates(templates)


def templates() -> dict:
    return load_templates()


def predictable(intent: str) -> dict | None:
    tpl = load_templates().get(intent)
    if intent in NEVER_PREDICT or not tpl or tpl.get("stable", 0) < STABLE_USES:
        return None
    return tpl
