import json
import time

from config import STATE_DIR

FILE = STATE_DIR / "autonomy_journal.json"
KEEP = 400


def _load() -> list[dict]:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def write(kind: str, title: str, text: str, steps: list | None = None) -> dict:
    entry = {"at": time.time(), "kind": kind, "title": title[:120], "text": text[:1500],
             "steps": [{"tool": s.get("tool"), "result": str(s.get("result", ""))[:300]} for s in (steps or [])][-10:]}
    items = _load()
    items.append(entry)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(items[-KEEP:], ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(FILE)
    return entry


def recent(limit: int = 80, since: float = 0) -> list[dict]:
    return [e for e in _load() if e["at"] >= since][-limit:][::-1]
