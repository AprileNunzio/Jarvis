import hashlib
import hmac
import json
import os
import re
import secrets
import time

from config import STATE_DIR, node_keys, read_global_env

NODES_FILE = STATE_DIR / "nodes.json"
PAIR_TTL = 600
OFFLINE_AFTER = 90
MAX_NODES = 64
TYPES = {"satellite": "Satellite audio", "display": "Display", "server": "Server Jarvis", "esp32": "Microcontrollore",
         "android": "Android", "sensor": "Sensore", "other": "Altro"}
COMMANDS = {"identify": "Identificati", "restart": "Riavvia l'agente", "update": "Aggiorna", "reboot": "Riavvia il dispositivo"}
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,47}$")
_TEXT_RE = re.compile(r"[^\w\s.,:;@()/+\-'’àèéìòù]", re.U)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def clean_text(value, limit: int = 60) -> str:
    return _TEXT_RE.sub("", str(value or "")).strip()[:limit]


def clean_id(value) -> str:
    node_id = str(value or "").strip().lower()
    if not _ID_RE.match(node_id):
        raise ValueError("Identificativo del nodo non valido")
    return node_id


class Registry:
    def __init__(self) -> None:
        self.data = self._load()
        self.pairing: dict[str, float] = {}

    @staticmethod
    def _load() -> dict:
        if not NODES_FILE.exists():
            return {"nodes": {}}
        return json.loads(NODES_FILE.read_text(encoding="utf-8"))

    def _save(self) -> None:
        tmp = NODES_FILE.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(self.data, handle, ensure_ascii=False, indent=1)
        os.replace(tmp, NODES_FILE)

    def new_code(self) -> dict:
        now = time.time()
        self.pairing = {c: t for c, t in self.pairing.items() if t > now}
        code = f"{secrets.randbelow(1_000_000):06d}"
        self.pairing[code] = now + PAIR_TTL
        return {"code": code, "expires_in": PAIR_TTL}

    def pair(self, code: str, node_id: str, info: dict) -> str:
        expires = self.pairing.pop(str(code), 0)
        if expires < time.time():
            raise PermissionError("Codice di abbinamento non valido o scaduto")
        node_id = clean_id(node_id)
        if node_id not in self.data["nodes"] and len(self.data["nodes"]) >= MAX_NODES:
            raise ValueError("Numero massimo di nodi raggiunto")
        token = secrets.token_urlsafe(32)
        kind = info.get("type") if info.get("type") in TYPES else "other"
        self.data["nodes"][node_id] = {"id": node_id, "name": clean_text(info.get("name")) or node_id, "type": kind,
                                       "room": clean_text(info.get("room")), "token": _hash(token),
                                       "paired_at": time.time(), "last_seen": 0, "commands": []}
        self._save()
        return token

    def authenticate(self, node_id: str, token: str) -> dict:
        node = self.data["nodes"].get(str(node_id))
        if not node or not hmac.compare_digest(node["token"], _hash(str(token))):
            raise PermissionError("Nodo non autorizzato")
        return node

    def heartbeat(self, node: dict, report: dict, ip: str) -> list[str]:
        metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else {}
        node.update(last_seen=time.time(), ip=ip, version=clean_text(report.get("version"), 40),
                    hostname=clean_text(report.get("hostname"), 60),
                    capabilities=[clean_text(c, 30) for c in (report.get("capabilities") or [])[:12]],
                    metrics={k: round(float(v), 1) for k, v in metrics.items()
                             if k in ("cpu", "ram", "disk", "temp", "uptime") and isinstance(v, (int, float))})
        commands, node["commands"] = node.get("commands", []), []
        self._save()
        return commands

    def update(self, node_id: str, changes: dict) -> dict:
        node = self.data["nodes"][clean_id(node_id)]
        if "name" in changes:
            node["name"] = clean_text(changes["name"]) or node["id"]
        if "room" in changes:
            node["room"] = clean_text(changes["room"])
        if "settings" in changes:
            node["settings"] = self._settings(node.get("settings") or {}, changes["settings"])
        self._save()
        return node

    @staticmethod
    def _settings(current: dict, wanted) -> dict:
        allowed = set(node_keys())
        if wanted == "reset":
            return {}
        if wanted == "copy_all":
            env = read_global_env()
            return {k: env[k] for k in allowed if env.get(k)}
        if not isinstance(wanted, dict):
            raise ValueError("Impostazioni non valide")
        out = dict(current)
        for key, value in wanted.items():
            if key not in allowed:
                raise ValueError(f"{key} non si può personalizzare per nodo")
            value = "" if value is None else str(value).strip()
            if "\n" in value or len(value) > 500:
                raise ValueError(f"Valore non valido per {key}")
            if value:
                out[key] = value
            else:
                out.pop(key, None)
        return out

    def effective(self, node_id: str) -> dict:
        node = self.data["nodes"][clean_id(node_id)]
        env = read_global_env()
        base = {k: env.get(k, "") for k in node_keys()}
        return {**base, **(node.get("settings") or {})}

    def command(self, node_id: str, command: str) -> None:
        if command not in COMMANDS:
            raise ValueError("Comando sconosciuto")
        node = self.data["nodes"][clean_id(node_id)]
        node["commands"] = list(dict.fromkeys([*node.get("commands", []), command]))[:5]
        self._save()

    def remove(self, node_id: str) -> None:
        self.data["nodes"].pop(clean_id(node_id), None)
        self._save()

    def listing(self) -> list[dict]:
        now = time.time()
        out = []
        for node in self.data["nodes"].values():
            public = {k: v for k, v in node.items() if k != "token"}
            public["online"] = now - node.get("last_seen", 0) < OFFLINE_AFTER
            public["type_label"] = TYPES.get(node["type"], node["type"])
            out.append(public)
        return sorted(out, key=lambda n: (not n["online"], n["name"].lower()))


registry = Registry()
