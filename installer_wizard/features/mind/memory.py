import json
import time
import uuid

from config import STATE_DIR

from features.mind import text as T

MIND_DIR = STATE_DIR / "mind"
FACTS_FILE = MIND_DIR / "facts.json"
MAX_FACTS = 400


class LongTermMemory:
    def __init__(self) -> None:
        MIND_DIR.mkdir(parents=True, exist_ok=True)
        self.facts: list = []
        try:
            self.facts = json.loads(FACTS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.facts = []

    def save(self) -> None:
        tmp = FACTS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.facts, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(FACTS_FILE)

    def add(self, text: str, kind: str = "fatto", score: float = 0.6, who: str = "") -> dict | None:
        text = " ".join(text.split())[:200]
        if len(text) < 3:
            return None
        for f in self.facts:
            if T.jaccard(f["text"], text) >= 0.6:
                f.update(text=text, score=max(f["score"], score), updated=time.time(),
                         hits=f.get("hits", 0), who=who or f.get("who", ""))
                self.save()
                return f
        fact = {"id": uuid.uuid4().hex[:8], "text": text, "kind": kind, "score": round(score, 2),
                "who": who, "created": time.time(), "updated": time.time(), "hits": 0}
        self.facts.append(fact)
        self.facts.sort(key=lambda x: -x["score"])
        del self.facts[MAX_FACTS:]
        self.save()
        return fact

    def recall(self, query: str, k: int = 4, who: str = "") -> list:
        scored = []
        for f in self.facts:
            if who and f.get("who") and f["who"] != who:
                continue
            rel = T.overlap(query, f["text"])
            if rel >= 0.34:
                scored.append((rel * 0.7 + f["score"] * 0.3, f))
        scored.sort(key=lambda x: -x[0])
        hits = [f for _, f in scored[:k]]
        for f in hits:
            f["hits"] = f.get("hits", 0) + 1
        if hits:
            self.save()
        return hits

    def forget(self, fid: str) -> bool:
        before = len(self.facts)
        self.facts = [f for f in self.facts if f["id"] != fid]
        if len(self.facts) != before:
            self.save()
            return True
        return False

    def clear(self) -> int:
        n = len(self.facts)
        self.facts = []
        self.save()
        return n

    def listing(self) -> list:
        return sorted(self.facts, key=lambda x: -x["updated"])

    def stats(self) -> dict:
        kinds: dict = {}
        for f in self.facts:
            kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
        return {"count": len(self.facts), "kinds": kinds}
