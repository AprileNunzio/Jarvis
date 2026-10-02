import json
import time
import uuid

from config import STATE_DIR

FILE = STATE_DIR / "autonomy_approvals.json"
EXPIRE = 3 * 86400


def _load() -> list[dict]:
    try:
        items = json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [a for a in items if time.time() - a["at"] < EXPIRE]


def _save(items: list[dict]) -> None:
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(items[-50:], ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(FILE)


def add(title: str, summary: str, request: str, steps: list, tool: str, args: dict, routine: str = "") -> dict:
    item = {"id": uuid.uuid4().hex[:6], "at": time.time(), "title": title[:100], "summary": summary[:400],
            "request": request, "steps": steps, "tool": tool, "args": args, "routine": routine}
    items = _load()
    items.append(item)
    _save(items)
    return item


def pending() -> list[dict]:
    return _load()


def take(aid: str) -> dict:
    items = _load()
    found = next((a for a in items if a["id"] == aid), None)
    if not found:
        raise KeyError(aid)
    _save([a for a in items if a["id"] != aid])
    return found
