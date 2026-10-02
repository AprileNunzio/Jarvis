import time
from collections import Counter, deque

import numpy as np

from gallery import UNKNOWN


class Track:
    _next = 1

    def __init__(self, box) -> None:
        self.id = Track._next
        Track._next += 1
        self.box = box
        self.votes: deque = deque(maxlen=7)
        self.first_seen = self.last_seen = time.time()
        self.feature = None
        self.frames = 0
        self.samples: list = []
        self.last_learn = 0.0
        self.facing = False
        self.echo_of: str | None = None

    def identity(self) -> tuple[str | None, str, float]:
        if not self.votes:
            return None, UNKNOWN, 0.0
        (slug, name), count = Counter((v[0], v[1]) for v in self.votes).most_common(1)[0]
        scores = [v[2] for v in self.votes if v[0] == slug]
        return slug, name, float(np.mean(scores)) * count / len(self.votes)


def iou(a, b) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix, iy = max(ax, bx), max(ay, by)
    iw, ih = min(ax + aw, bx + bw) - ix, min(ay + ah, by + bh) - iy
    if iw <= 0 or ih <= 0:
        return 0.0
    inter = iw * ih
    return inter / (aw * ah + bw * bh - inter)


def facing(face) -> bool:
    rx, ry, lx, ly, nx = (float(v) for v in face[4:9])
    eyes = abs(lx - rx)
    return eyes > 1 and abs(nx - (rx + lx) / 2) / eyes < 0.22


def reliable_unknown(track: Track, now: float) -> bool:
    slug, _, _ = track.identity()
    return slug is None and len(track.votes) >= 3 and now - track.first_seen >= 1.5
