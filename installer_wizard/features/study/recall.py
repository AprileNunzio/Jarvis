import asyncio

import httpx
import numpy as np

from config import DEMO
from features.study.constants import LEVELS


class StudyRecall:
    async def recall_cells(self, query: str, k: int = 4, topic: str | None = None, min_score: float = 0.55) -> list:
        if not self.memory.ids:
            return []
        vec = (await self.embed([query], query=True))[0]
        return self.memory.search(np.asarray(vec, dtype=np.float32), k=k, min_score=min_score, topic=topic)

    async def recall(self, query: str) -> str:
        if DEMO or not self.settings.get("use_in_answers") or not self.memory.ids:
            return ""
        try:
            hits = await asyncio.wait_for(self.recall_cells(query, 4, min_score=0.62), 4)
        except (asyncio.TimeoutError, httpx.HTTPError, KeyError, ValueError):
            return ""
        return "\n".join(f"- [{h.get('topic_name', '')}] {h['text']}" for h in hits)[:1400]

    def dataset(self) -> list:
        rows = []
        for t in self.data["topics"].values():
            for n, lv in t["levels"].items():
                for lesson in lv.get("lessons", []):
                    if lesson["status"] != "done" and not lesson.get("summary"):
                        continue
                    if lesson.get("summary"):
                        rows.append({"instruction": f"Spiegami «{lesson['title']}» ({t['name']}, livello {LEVELS[int(n)]}).",
                                     "input": "", "output": lesson["summary"]})
                    for q in lesson.get("questions", []):
                        rows.append({"instruction": q["q"], "input": "", "output": q["a"]})
                    for e in lesson.get("exercises", []):
                        rows.append({"instruction": f"Risolvi: {e['q']}", "input": "", "output": e["a"]})
                    if lesson.get("facts"):
                        rows.append({"instruction": f"Elenca i concetti chiave di «{lesson['title']}».", "input": "",
                                     "output": "\n".join(f"- {f}" for f in lesson["facts"])})
        return rows
