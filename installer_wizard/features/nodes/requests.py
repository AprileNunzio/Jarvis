import hashlib
import hmac
import re
import time

from features.nodes.registry import TYPES, clean_id, clean_text, registry

TTL = 15 * 60
MAX_PENDING = 16
_KEY_RE = re.compile(r"^[0-9a-f]{64}$")


def fingerprint(key: str) -> str:
    return f"{int(hashlib.sha256(key.encode()).hexdigest(), 16) % 1_000_000:06d}"


class PairingRequests:

    def __init__(self) -> None:
        self.pending: dict[str, dict] = {}

    def _prune(self) -> None:
        now = time.time()
        self.pending = {k: v for k, v in self.pending.items() if v["expires"] > now}

    def submit(self, body: dict, ip: str) -> dict:
        self._prune()
        node_id, key = clean_id(body.get("id")), str(body.get("key") or "")
        if not _KEY_RE.match(key):
            raise ValueError("Chiave del nodo non valida")
        if node_id not in self.pending and len(self.pending) >= MAX_PENDING:
            raise ValueError("Troppe richieste in attesa")
        current = self.pending.get(node_id)
        if current and not hmac.compare_digest(current["key"], hashlib.sha256(key.encode()).hexdigest()):
            raise PermissionError("Un altro dispositivo sta già chiedendo di abbinarsi con questo nome")
        kind = body.get("type") if body.get("type") in TYPES else "other"
        self.pending[node_id] = {"id": node_id, "name": clean_text(body.get("name")) or node_id, "type": kind,
                                 "room": clean_text(body.get("room")), "ip": ip, "at": time.time(),
                                 "expires": time.time() + TTL, "key": hashlib.sha256(key.encode()).hexdigest(),
                                 "fingerprint": fingerprint(key), "approved": False, "token": ""}
        return {"fingerprint": fingerprint(key), "expires_in": TTL}

    def approve(self, node_id: str) -> dict:
        self._prune()
        req = self.pending.get(node_id)
        if not req:
            raise KeyError(node_id)
        code = registry.new_code()["code"]
        req["token"] = registry.pair(code, node_id, req)
        req["approved"] = True
        return req

    def reject(self, node_id: str) -> None:
        self.pending.pop(node_id, None)

    def claim(self, node_id: str, key: str) -> str | None:
        self._prune()
        req = self.pending.get(node_id)
        if not req or not hmac.compare_digest(req["key"], hashlib.sha256(str(key).encode()).hexdigest()):
            raise PermissionError("Richiesta sconosciuta o scaduta")
        if not req["approved"]:
            return None
        self.pending.pop(node_id, None)
        return req["token"]

    def listing(self) -> list[dict]:
        self._prune()
        return [{k: v for k, v in r.items() if k not in ("key", "token")} for r in self.pending.values()
                if not r["approved"]]


requests = PairingRequests()
