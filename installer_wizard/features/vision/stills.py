import secrets
from collections import OrderedDict

KEEP = 8
_stills: OrderedDict[str, bytes] = OrderedDict()


def keep(jpeg: bytes) -> str:
    sid = secrets.token_hex(8)
    _stills[sid] = jpeg
    while len(_stills) > KEEP:
        _stills.popitem(last=False)
    return sid


def get(sid: str) -> bytes | None:
    return _stills.get(sid)


def url(sid: str) -> str:
    return f"/api/vision/still/{sid}.jpg"


def norm_box(box) -> list[float] | None:
    try:
        x, y, w, h = (float(v) for v in box[:4])
    except (TypeError, ValueError):
        return None
    if max(x, y, w, h) > 1.5:
        return None
    x, y = min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0)
    w, h = min(max(w, 0.0), 1.0 - x), min(max(h, 0.0), 1.0 - y)
    return [round(x, 4), round(y, 4), round(w, 4), round(h, 4)] if w > 0.005 and h > 0.005 else None


def pixel_box(box: list[int], width: int = 640, height: int = 480) -> list[float] | None:
    x, y, w, h = box
    return norm_box([x / width, y / height, w / width, h / height])
