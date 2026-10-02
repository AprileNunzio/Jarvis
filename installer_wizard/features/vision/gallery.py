import json
import logging
import os
import re
import shutil
import threading
import time
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger("jarvis.vision")

FACES = Path(os.environ.get("JARVIS_FACES_DIR", "/var/lib/jarvis/faces"))
MATCH_THRESHOLD = float(os.environ.get("JARVIS_FACE_THRESHOLD", "0.40"))
UNKNOWN = "Sconosciuto"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "persona"


class Gallery:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.people: dict = {}
        self.reload()

    def reload(self) -> None:
        people = {}
        FACES.mkdir(parents=True, exist_ok=True)
        for d in FACES.iterdir():
            try:
                meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
                emb = np.load(d / "embeddings.npy")
                emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)
                people[d.name] = {**meta, "slug": d.name, "embeddings": emb}
            except (OSError, ValueError, KeyError):
                continue
        with self.lock:
            self.people = people
        log.info("Galleria: %d persone registrate", len(people))

    def match(self, feature: np.ndarray) -> tuple[str, str, float]:
        f = feature / np.linalg.norm(feature)
        best = (None, UNKNOWN, 0.0)
        with self.lock:
            for slug, p in self.people.items():
                score = float(np.max(p["embeddings"] @ f))
                if score > best[2]:
                    best = (slug, p["name"], score)
        return best if best[2] >= MATCH_THRESHOLD else (None, UNKNOWN, best[2])

    def closest(self, feature: np.ndarray) -> tuple[str | None, float]:
        f = feature / np.linalg.norm(feature)
        best = (None, 0.0)
        with self.lock:
            for slug, p in self.people.items():
                score = float(np.max(p["embeddings"] @ f))
                if score > best[1]:
                    best = (slug, score)
        return best

    def next_guest_name(self) -> str:
        with self.lock:
            used = {p["name"] for p in self.people.values()}
        n = 1
        while f"Ospite {n}" in used:
            n += 1
        return f"Ospite {n}"

    def add_samples(self, slug: str, embeddings: list) -> None:
        d = FACES / slug
        try:
            old = list(np.load(d / "embeddings.npy"))
            meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        merged = (old + embeddings)[-40:]
        np.save(d / "embeddings.npy", np.array(merged, dtype=np.float32))
        meta["samples"] = len(merged)
        (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        self.reload()

    def rename(self, slug: str, name: str) -> dict | None:
        d = FACES / slug
        try:
            meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        meta.update(name=name, auto=False, renamed_at=time.time())
        (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        self.reload()
        return {**meta, "slug": slug}

    def save(self, name: str, embeddings: list, photo: np.ndarray, auto: bool = False, slug: str | None = None) -> dict:
        slug = slug or slugify(name)
        d = FACES / slug
        d.mkdir(parents=True, exist_ok=True)
        old = []
        if (d / "embeddings.npy").exists():
            old = list(np.load(d / "embeddings.npy"))
        np.save(d / "embeddings.npy", np.array((old + embeddings)[-40:], dtype=np.float32))
        cv2.imwrite(str(d / "photo.jpg"), photo)
        meta = {"name": name, "enrolled_at": time.time(), "samples": min(40, len(old) + len(embeddings)), "auto": auto}
        (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        os.chmod(d, 0o700)
        self.reload()
        return {**meta, "slug": slug}

    def delete(self, slug: str) -> bool:
        d = FACES / slug
        if not d.is_dir() or d.parent != FACES:
            return False
        shutil.rmtree(d)
        self.reload()
        return True

    def listing(self) -> list:
        with self.lock:
            return [{k: v for k, v in p.items() if k != "embeddings"} for p in self.people.values()]
