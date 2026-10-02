import json
import logging
import os
import re
import time
import unicodedata
from pathlib import Path

log = logging.getLogger("jarvis.ear")

WAKE_RE = re.compile(r"\b(hey |ehi |ei |ok |okay )?(jarvis|jarvi|giarvis|jervis|jarviss|giavis|gervis|jarvys)\b[\s,.!?:;-]*", re.I)
LEARN_FILE = Path(os.environ.get("JARVIS_EAR_LEARN", "/var/lib/jarvis/ear_learning.json"))
PEOPLE_DIR = Path(os.environ.get("JARVIS_PEOPLE_DIR", "/var/lib/jarvis/people"))
TOKEN_RE = re.compile(r"[a-zàèéìòù']+", re.I)


def _plain(word: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", word.lower()) if unicodedata.category(c) != "Mn")


def _lev(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


class Learner:

    def __init__(self) -> None:
        self.data = {"variants": {}, "stats": {"wakes": 0, "fuzzy_wakes": 0, "commands": 0, "false_wakes": 0,
                                               "learned": 0, "wake_ms": []}, "strict": False}
        try:
            self.data.update(json.loads(LEARN_FILE.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
        self.recent_miss = None
        self.last_save = 0.0

    def save(self, force: bool = False) -> None:
        if not force and time.time() - self.last_save < 10:
            return
        self.last_save = time.time()
        try:
            LEARN_FILE.parent.mkdir(parents=True, exist_ok=True)
            LEARN_FILE.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError as exc:
            log.warning("Apprendimento non salvato: %s", exc)

    def hotwords(self) -> str:
        names = {"Jarvis"}
        try:
            for f in list(PEOPLE_DIR.glob("*.json"))[:50]:
                first = json.loads(f.read_text(encoding="utf-8")).get("first_name")
                if first and not first.lower().startswith("ospite"):
                    names.add(first)
        except (OSError, ValueError):
            pass
        return " ".join(sorted(names))

    def find_wake(self, text: str):
        exact = WAKE_RE.search(text)
        if exact:
            return exact.start(), exact.end(), None
        tokens = list(TOKEN_RE.finditer(text))
        window = tokens[:2] if self.data.get("strict") else tokens[:4]
        for m in window:
            word = _plain(m.group())
            if len(word) < 4 or len(word) > 9:
                continue
            learned = self.data["variants"].get(word, 0)
            dist = _lev(word, "jarvis")
            if dist <= 1 or learned >= 2 or (dist == 2 and learned >= 1):
                end = m.end()
                while end < len(text) and text[end] in " ,.!?:;-":
                    end += 1
                return m.start(), end, word
        return None

    def on_wake(self, variant, ms: int) -> None:
        s = self.data["stats"]
        s["wakes"] += 1
        s["wake_ms"] = (s.get("wake_ms", []) + [ms])[-50:]
        if variant:
            s["fuzzy_wakes"] += 1
            self.data["variants"][variant] = self.data["variants"].get(variant, 0) + 1
        self.save()

    def on_command(self) -> None:
        self.data["stats"]["commands"] += 1
        self.save()

    def on_false_wake(self) -> None:
        s = self.data["stats"]
        s["false_wakes"] += 1
        total = max(1, s["wakes"])
        self.data["strict"] = total >= 10 and s["false_wakes"] / total > 0.3
        self.save()

    def on_miss(self, text: str) -> None:
        tokens = TOKEN_RE.findall(text)
        if tokens:
            self.recent_miss = (time.time(), _plain(tokens[0]))

    def on_manual_listen(self) -> None:
        if self.recent_miss and time.time() - self.recent_miss[0] < 8:
            word = self.recent_miss[1]
            if 3 <= len(word) <= 10 and _lev(word, "jarvis") <= 3:
                self.data["variants"][word] = self.data["variants"].get(word, 0) + 1
                self.data["stats"]["learned"] += 1
                log.info("Imparata la variante «%s» per Jarvis", word)
                self.save(force=True)
        self.recent_miss = None

    def summary(self) -> dict:
        s = self.data["stats"]
        ms = s.get("wake_ms") or [0]
        return {"wakes": s["wakes"], "commands": s["commands"], "false_wakes": s["false_wakes"],
                "fuzzy_wakes": s["fuzzy_wakes"], "avg_wake_ms": int(sum(ms) / len(ms)),
                "variants": {k: v for k, v in sorted(self.data["variants"].items(), key=lambda x: -x[1])[:15]},
                "strict": self.data.get("strict", False)}


learner = Learner()
