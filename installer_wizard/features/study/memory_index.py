import json
import threading
import time
from pathlib import Path

import numpy as np

_POPCOUNT = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint16)
DUPLICATE = 0.95


def _popcount_rows(x: np.ndarray) -> np.ndarray:
    if hasattr(np, "bitwise_count"):
        return np.bitwise_count(x).sum(axis=1, dtype=np.int32)
    return _POPCOUNT[x].sum(axis=1, dtype=np.int32)


def encode(vec: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    v = np.asarray(vec, dtype=np.float32)
    v = v / (np.linalg.norm(v) + 1e-9)
    tau = 0.5 * float(np.mean(np.abs(v)))
    return (np.packbits(v > 0), np.packbits(v > tau), np.packbits(v < -tau), v.astype(np.float16))


class MemoryIndex:
    def __init__(self, directory: Path) -> None:
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.dim = 0
        self.ids: list = []
        self.meta: dict = {}
        self.bin = self.pos = self.neg = self.vec = None
        self.dirty = False
        self.last_search: dict = {}
        self._load()

    def _load(self) -> None:
        try:
            self.meta = json.loads((self.dir / "cells.json").read_text(encoding="utf-8"))
            self.ids = json.loads((self.dir / "ids.json").read_text(encoding="utf-8"))
            arrays = np.load(self.dir / "index.npz")
            self.bin, self.pos, self.neg, self.vec = arrays["bin"], arrays["pos"], arrays["neg"], arrays["vec"]
            self.dim = int(self.vec.shape[1]) if len(self.ids) else 0
            if not (len(self.ids) == len(self.bin) == len(self.vec)):
                raise ValueError("indice incoerente")
        except (OSError, ValueError, KeyError):
            self.ids, self.meta, self.dim = [], {}, 0
            self.bin = self.pos = self.neg = self.vec = None

    def save(self, force: bool = False) -> None:
        with self.lock:
            if not (self.dirty or force):
                return
            tmp = self.dir / "index.tmp.npz"
            if self.ids:
                np.savez(tmp, bin=self.bin, pos=self.pos, neg=self.neg, vec=self.vec)
                tmp.replace(self.dir / "index.npz")
            for name, data in (("cells.json", self.meta), ("ids.json", self.ids)):
                t = self.dir / (name + ".tmp")
                t.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                t.replace(self.dir / name)
            self.dirty = False

    def _cosines(self, rows: np.ndarray, q: np.ndarray) -> np.ndarray:
        return self.vec[rows].astype(np.float32) @ q

    def add(self, cell_id: str, vec, text: str, **meta) -> tuple[str, bool]:
        b, p, n, f = encode(vec)
        q = f.astype(np.float32)
        with self.lock:
            if self.ids:
                if len(q) != self.dim:
                    raise ValueError(f"dimensione del vettore {len(q)} diversa dalla memoria ({self.dim})")
                cand = self._candidates(b, p, n, 32, 8)
                if len(cand):
                    cos = self._cosines(cand, q)
                    best = int(np.argmax(cos))
                    if cos[best] > DUPLICATE:
                        existing = self.ids[cand[best]]
                        m = self.meta[existing]
                        m["strength"] = m.get("strength", 1) + 1
                        m["reinforced"] = time.time()
                        self.dirty = True
                        return existing, False
                self.bin = np.vstack([self.bin, b])
                self.pos = np.vstack([self.pos, p])
                self.neg = np.vstack([self.neg, n])
                self.vec = np.vstack([self.vec, f])
            else:
                self.dim = len(q)
                self.bin, self.pos, self.neg, self.vec = b[None], p[None], n[None], f[None]
            self.ids.append(cell_id)
            self.meta[cell_id] = {"text": text, "strength": 1, "created": time.time(), "used": 0, **meta}
            self.dirty = True
            return cell_id, True

    def remove_where(self, **match) -> int:
        with self.lock:
            keep = [i for i, cid in enumerate(self.ids)
                    if not all(self.meta.get(cid, {}).get(k) == v for k, v in match.items())]
            removed = len(self.ids) - len(keep)
            if removed:
                keep_set = set(keep)
                for i, cid in enumerate(self.ids):
                    if i not in keep_set:
                        self.meta.pop(cid, None)
                self.ids = [self.ids[i] for i in keep]
                if keep:
                    self.bin, self.pos, self.neg, self.vec = (a[keep] for a in (self.bin, self.pos, self.neg, self.vec))
                else:
                    self.bin = self.pos = self.neg = self.vec = None
                    self.dim = 0
                    for f in ("index.npz",):
                        (self.dir / f).unlink(missing_ok=True)
                self.dirty = True
            return removed

    def _candidates(self, b, p, n, k_bin: int, k_ter: int) -> np.ndarray:
        total = len(self.ids)
        ham = _popcount_rows(np.bitwise_xor(self.bin, b))
        k1 = min(total, k_bin)
        rows = np.argpartition(ham, k1 - 1)[:k1] if k1 < total else np.arange(total)
        pp, nn = self.pos[rows], self.neg[rows]
        score = (_popcount_rows(pp & p) + _popcount_rows(nn & n)
                 - _popcount_rows(pp & n) - _popcount_rows(nn & p))
        k2 = min(len(rows), k_ter)
        top = np.argpartition(-score, k2 - 1)[:k2] if k2 < len(rows) else np.arange(len(rows))
        return rows[top]

    def search(self, vec, k: int = 5, min_score: float = 0.0, topic: str | None = None) -> list:
        if not self.ids:
            return []
        t0 = time.perf_counter()
        b, p, n, f = encode(vec)
        q = f.astype(np.float32)
        with self.lock:
            if len(q) != self.dim:
                return []
            t1 = time.perf_counter()
            rows = self._candidates(b, p, n, 256, 48)
            t2 = time.perf_counter()
            cos = self._cosines(rows, q)
            order = np.argsort(-cos)
            out = []
            for i in order:
                cid = self.ids[rows[i]]
                m = self.meta.get(cid, {})
                if cos[i] < min_score or (topic and m.get("topic") != topic):
                    continue
                m["used"] = m.get("used", 0) + 1
                out.append({"id": cid, "score": round(float(cos[i]), 4), **m})
                if len(out) >= k:
                    break
            t3 = time.perf_counter()
        self.last_search = {"cells": len(self.ids), "binary_ternary_ms": round((t2 - t1) * 1000, 2),
                            "exact_ms": round((t3 - t2) * 1000, 2), "total_ms": round((t3 - t0) * 1000, 2)}
        return out

    def stats(self) -> dict:
        n = len(self.ids)
        return {"cells": n, "dim": self.dim,
                "binary_bytes": int(self.bin.nbytes) if n else 0,
                "ternary_bytes": int(self.pos.nbytes + self.neg.nbytes) if n else 0,
                "float_bytes": int(self.vec.nbytes) if n else 0,
                "last_search": self.last_search}
