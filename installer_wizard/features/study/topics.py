import time
import uuid

from features.study.constants import LEVELS, slug


class StudyTopics:
    def add_topic(self, name: str, source: str = "manual", target_level: int = 4, priority: int = 3,
                  focus: str = "", status: str = "active") -> dict:
        name = " ".join(name.split())[:60]
        if not name:
            raise ValueError("Nome della materia mancante")
        existing = self.find_topic(name)
        if existing:
            if source == "manual" and existing["status"] == "proposed":
                existing["status"] = "active"
            return existing
        tid = slug(name)
        while tid in self.data["topics"]:
            tid += "-" + uuid.uuid4().hex[:3]
        topic = {"id": tid, "name": name[:1].upper() + name[1:], "source": source, "status": status,
                 "priority": max(1, min(5, int(priority))), "target_level": max(1, min(5, int(target_level))),
                 "level": 1, "levels": {}, "interest": 0.0, "mentions": 0, "hints": [], "focus": focus[:300],
                 "created": time.time(), "last_studied": 0, "seconds": 0}
        self.data["topics"][tid] = topic
        self.journal(f"Nuova materia: {topic['name']} ({'scelta da te' if source == 'manual' else 'dalle conversazioni'})")
        self.save()
        return topic

    def find_topic(self, name: str) -> dict | None:
        key = slug(name)
        for t in self.data["topics"].values():
            if slug(t["name"]) == key:
                return t
        return None

    def update_topic(self, tid: str, changes: dict) -> dict:
        t = self.data["topics"][tid]
        for k in ("priority", "target_level"):
            if k in changes:
                t[k] = max(1, min(5, int(changes[k])))
        if "status" in changes and changes["status"] in ("active", "paused", "proposed", "done"):
            t["status"] = changes["status"]
            if t["status"] == "active" and t["level"] > t["target_level"]:
                t["target_level"] = min(5, t["level"])
        if "focus" in changes:
            t["focus"] = str(changes["focus"])[:300]
        if "name" in changes and str(changes["name"]).strip():
            t["name"] = str(changes["name"]).strip()[:60]
        if t["level"] <= t["target_level"] and t["status"] == "done":
            t["status"] = "active"
        self.save()
        return t

    def delete_topic(self, tid: str) -> None:
        self.data["topics"].pop(tid, None)
        self.memory.remove_where(topic=tid)
        self.save()

    def reset_topic(self, tid: str) -> dict:
        t = self.data["topics"][tid]
        t.update(level=1, levels={}, last_studied=0, seconds=0)
        if t["status"] == "done":
            t["status"] = "active"
        self.memory.remove_where(topic=tid)
        self.save()
        return t

    @staticmethod
    def _questions(level: dict) -> list:
        return [q for lesson in level.get("lessons", []) for q in lesson.get("questions", [])]

    def mastery(self, topic: dict, lvl: int) -> float | None:
        level = topic["levels"].get(str(lvl))
        if not level:
            return None
        scores = [q["last_score"] for q in self._questions(level) if q.get("last_score") is not None]
        return round(sum(scores) / len(scores), 3) if scores else None

    def level_progress(self, topic: dict, lvl: int) -> float:
        if lvl < topic["level"]:
            return 1.0
        level = topic["levels"].get(str(lvl))
        if not level or not level.get("lessons"):
            return 0.0
        if level.get("passed_at"):
            return 1.0
        lessons = level["lessons"]
        done = sum(1 for x in lessons if x["status"] == "done") / len(lessons)
        m = self.mastery(topic, lvl)
        return round(min(0.99, done * 0.75 + (m or 0) * 0.25), 3)

    def overview(self, topic: dict) -> dict:
        target = topic["target_level"]
        levels = [{"level": n, "name": LEVELS[n], "progress": self.level_progress(topic, n),
                   "mastery": self.mastery(topic, n),
                   "lessons": len(topic["levels"].get(str(n), {}).get("lessons", [])),
                   "done": sum(1 for x in topic["levels"].get(str(n), {}).get("lessons", []) if x["status"] == "done")}
                  for n in LEVELS]
        overall = sum(lv["progress"] for lv in levels[:target]) / target
        cells = sum(1 for m in self.memory.meta.values() if m.get("topic") == topic["id"])
        due = sum(1 for lv in topic["levels"].values() for q in self._questions(lv) if q.get("due", 0) <= time.time())
        level_name = (f"obiettivo raggiunto ({LEVELS[target]})" if topic["status"] == "done"
                      else LEVELS.get(topic["level"], "Esperto"))
        return {**{k: v for k, v in topic.items() if k != "levels"}, "level_name": level_name,
                "levels_detail": levels, "progress": round(overall, 3), "cells": cells, "due_reviews": due,
                "interest_now": round(self._interest(topic), 2)}

    def topic_detail(self, tid: str) -> dict:
        t = self.data["topics"][tid]
        return {**self.overview(t), "levels": t["levels"]}
