import json
import time

from config import ETC_DIR, env_get, write_env
from sealed import SealedFile
from state import store

from features.google.constants import SERVICES, STATE_FILE
from features.people import identity

_store = SealedFile(ETC_DIR / "google_accounts.vault", ETC_DIR / "google.key")


class Accounts:
    def __init__(self) -> None:
        self._data: dict | None = None

    def _all(self) -> dict:
        if self._data is None:
            self._data = _store.load()
            self._migrate()
        return self._data

    def _migrate(self) -> None:
        legacy = env_get("JARVIS_GOOGLE_REFRESH_TOKEN", "")
        target = identity.owner() if legacy else None
        if not target:
            return
        info = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}
        self._data.setdefault(target["slug"], {
            "refresh": legacy, "email": info.get("email", ""), "name": info.get("name", ""),
            "scopes": info.get("scopes", []), "linked_at": info.get("linked_at", time.time())})
        _store.save(self._data)
        write_env({"JARVIS_GOOGLE_REFRESH_TOKEN": ""})
        store.event("INFO", f"Google: l'account collegato ora appartiene a {target.get('name')}", "google")

    def get(self, slug: str) -> dict | None:
        entry = self._all().get(slug)
        return dict(entry) if entry else None

    def slugs(self) -> list[str]:
        return list(self._all())

    def put(self, slug: str, entry: dict) -> None:
        data = self._all()
        data[slug] = {**data.get(slug, {}), **entry}
        _store.save(data)

    def remove(self, slug: str) -> dict | None:
        data = self._all()
        entry = data.pop(slug, None)
        _store.save(data)
        return entry

    @staticmethod
    def granted(entry: dict) -> list[str]:
        scopes = set(entry.get("scopes", []))
        return [s for s, d in SERVICES.items() if all(x in scopes for x in d["scopes"])]


accounts = Accounts()
