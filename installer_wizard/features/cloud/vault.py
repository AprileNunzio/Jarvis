import re

from config import ETC_DIR, read_env
from sealed import SealedFile

from features.cloud.catalog import BY_ID, OPTION_CHOICES, SERVER, sync_servers

KEY_FILE = ETC_DIR / "cloud.key"
VAULT_FILE = ETC_DIR / "cloud.vault"
_SEALED = SealedFile(VAULT_FILE, KEY_FILE)
LEGACY = {"gemini": "GEMINI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
_URL_RE = re.compile(r"^https?://[A-Za-z0-9.\-:\[\]]+(/[A-Za-z0-9._~\-/%]*)?$")
_SECRET_RE = re.compile(r"^[\x21-\x7e]{8,512}$")
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+\-]{0,159}$")


class Vault:
    def __init__(self) -> None:
        self._cache: dict | None = None

    def _load(self) -> dict:
        if self._cache is None:
            data = _SEALED.load()
            self._cache = self._import_legacy(data)
            sync_servers(self._cache)
        return self._cache

    def _import_legacy(self, data: dict) -> dict:
        env = read_env()
        changed = False
        for pid, key in LEGACY.items():
            if env.get(key) and not data.get(pid, {}).get("key"):
                data.setdefault(pid, {})["key"] = env[key]
                changed = True
        if changed:
            self._persist(data)
        return data

    def _persist(self, data: dict) -> None:
        _SEALED.save(data)
        self._cache = data
        sync_servers(data)

    def servers(self) -> dict:
        return {pid: dict(e) for pid, e in self._load().items() if pid.startswith(SERVER)}

    def add_server(self, name: str, flavor: str, root: str, base_url: str, key: str) -> str:
        data = self._load()
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:24] or "server"
        pid, n = f"{SERVER}{slug}", 2
        while pid in data:
            pid, n = f"{SERVER}{slug}-{n}", n + 1
        if key and not _SECRET_RE.match(key):
            raise ValueError("Chiave API non valida")
        if not _URL_RE.match(base_url):
            raise ValueError("Indirizzo non valido")
        data[pid] = {"name": name[:40], "flavor": flavor, "root": root, "base_url": base_url, "key": key}
        self._persist(data)
        return pid

    def remove_server(self, pid: str) -> None:
        data = self._load()
        if pid.startswith(SERVER) and data.pop(pid, None) is not None:
            self._persist(data)

    def get(self, pid: str) -> dict:
        return dict(self._load().get(pid, {}))

    def configured(self, pid: str) -> bool:
        entry, spec = self._load().get(pid, {}), BY_ID.get(pid)
        if not spec or not entry.get("enabled", True):
            return False
        has_key = bool(entry.get("key")) or spec.key_optional
        has_url = bool(entry.get("base_url") or spec.base_url)
        return has_key and has_url

    def update(self, pid: str, changes: dict) -> None:
        if pid not in BY_ID:
            raise KeyError(pid)
        data = self._load()
        entry = dict(data.get(pid, {}))
        if "key" in changes:
            key = str(changes["key"] or "").strip()
            if key and not _SECRET_RE.match(key):
                raise ValueError("Chiave API non valida")
            entry["key"] = key
        if "base_url" in changes:
            url = str(changes["base_url"] or "").strip().rstrip("/")
            if url and not _URL_RE.match(url):
                raise ValueError("Indirizzo non valido")
            entry["base_url"] = url
        if "model" in changes:
            model = str(changes["model"] or "").strip()
            if model and not _MODEL_RE.match(model):
                raise ValueError("Nome del modello non valido")
            entry["model"] = model
        if "enabled" in changes:
            entry["enabled"] = bool(changes["enabled"])
        if "options" in changes:
            entry["options"] = self._clean_options(changes["options"] or {})
        data[pid] = entry
        self._persist(data)

    @staticmethod
    def _clean_options(options: dict) -> dict:
        clean = {}
        for name, value in options.items():
            value = str(value)
            if name in OPTION_CHOICES and value in OPTION_CHOICES[name] and value:
                clean[name] = value
        return clean

    def public(self, pid: str) -> dict:
        entry = self._load().get(pid, {})
        key = entry.get("key", "")
        return {
            "has_key": bool(key),
            "key_hint": f"••••{key[-4:]}" if len(key) >= 8 else "",
            "base_url": entry.get("base_url", ""),
            "enabled": entry.get("enabled", True),
            "model": entry.get("model", ""),
            "options": entry.get("options", {}),
        }


vault = Vault()
