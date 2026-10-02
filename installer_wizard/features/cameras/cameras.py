import re
import time
import uuid

from config import ETC_DIR, STATE_DIR
from sealed import SealedFile
from state import store

CAM_DIR = STATE_DIR / "cameras"
REGISTRY = SealedFile(CAM_DIR / "registry.vault", ETC_DIR / "cameras.key")
KINDS = ("webcam", "rtsp", "onvif", "hikvision")
RETENTIONS = (5, 15, 60)
_URL_RE = re.compile(r"^(?:rtsp|rtsps|http|https)://[^\s]{3,300}$", re.I)
_DEV_RE = re.compile(r"^(?:/dev/video\d+|\d+)$")


class Cameras:
    def __init__(self) -> None:
        CAM_DIR.mkdir(parents=True, exist_ok=True)
        self.items: dict = {}
        try:
            self.items = REGISTRY.load() or {}
        except Exception:
            self.items = {}
        self.publish()

    def save(self) -> None:
        REGISTRY.save(self.items)
        self.publish()

    def publish(self) -> None:
        recording = [c["id"] for c in self.items.values() if self._recording(c)]
        store.cameras = {"total": len(self.items), "recording": len(recording),
                         "nodes": sorted({c.get("node", "") for c in self.items.values() if c.get("node")})}
        store.touch()

    @staticmethod
    def _recording(c: dict) -> bool:
        return bool(c.get("enabled") and c.get("record") and c.get("consent"))

    def _validate(self, body: dict, base: dict) -> dict:
        name = " ".join(str(body.get("name", base.get("name", ""))).split())[:60]
        if not name:
            raise ValueError("Nome mancante")
        kind = body.get("kind", base.get("kind", "rtsp"))
        if kind not in KINDS:
            raise ValueError("Tipo non valido")
        url = str(body.get("url", base.get("url", ""))).strip()
        if kind == "webcam":
            if not _DEV_RE.match(url or "0"):
                url = "0"
        elif not _URL_RE.match(url):
            raise ValueError("URL della telecamera non valido")
        retention = int(body.get("retention_min", base.get("retention_min", 5)))
        if retention not in RETENTIONS:
            retention = 5
        return {"name": name, "kind": kind, "url": url, "node": str(body.get("node", base.get("node", "")))[:60],
                "retention_min": retention,
                "enabled": bool(body.get("enabled", base.get("enabled", False))),
                "record": bool(body.get("record", base.get("record", False))),
                "consent": bool(body.get("consent", base.get("consent", False)))}

    def add(self, body: dict) -> dict:
        data = self._validate(body, {})
        cid = uuid.uuid4().hex[:8]
        cam = {"id": cid, "created": time.time(), **data}
        self.items[cid] = cam
        self.save()
        store.event("INFO", f"Telecamera aggiunta: {cam['name']} ({cam['kind']})", "cameras")
        return cam

    def update(self, cid: str, body: dict) -> dict:
        if cid not in self.items:
            raise KeyError(cid)
        cam = self.items[cid]
        cam.update(self._validate(body, cam))
        self.save()
        return cam

    def delete(self, cid: str) -> None:
        if self.items.pop(cid, None) is None:
            raise KeyError(cid)
        self.save()
        store.event("INFO", f"Telecamera rimossa: {cid}", "cameras")

    @staticmethod
    def _safe(c: dict) -> dict:
        out = {k: v for k, v in c.items() if k != "url"}
        out["recording"] = Cameras._recording(c)
        out["has_url"] = bool(c.get("url"))
        return out

    def listing(self) -> dict:
        return {"cameras": [self._safe(c) for c in sorted(self.items.values(), key=lambda x: x.get("created", 0))],
                "kinds": list(KINDS), "retentions": list(RETENTIONS)}


cameras = Cameras()
