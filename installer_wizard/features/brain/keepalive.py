import json
import os
import re
from pathlib import Path

from config import STATE_DIR

CHOICES = ("5m", "30m", "1h", "6h", "24h", "-1")
_VALUE = re.compile(r"^(-1|\d{1,4}[smh])$")
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,159}$")
MAX_ENTRIES = 64


class KeepAlivePolicy:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._cache: tuple[int, dict[str, str]] = (-1, {})

    def overrides(self) -> dict[str, str]:
        try:
            stamp = self._path.stat().st_mtime_ns
        except OSError:
            return {}
        if stamp != self._cache[0]:
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raw = {}
            clean = {k: v for k, v in raw.items() if isinstance(raw, dict) and _REF.match(str(k)) and _VALUE.match(str(v))}
            self._cache = (stamp, clean)
        return dict(self._cache[1])

    def get(self, ref: str) -> str | None:
        return self.overrides().get(ref)

    def set_many(self, changes: dict[str, str | None]) -> dict[str, str]:
        current = self.overrides()
        for ref, value in changes.items():
            if not _REF.match(str(ref)):
                raise ValueError(f"invalid model: {ref}")
            if value in (None, ""):
                current.pop(ref, None)
            elif _VALUE.match(str(value)):
                current[ref] = str(value)
            else:
                raise ValueError(f"invalid duration: {value}")
        if len(current) > MAX_ENTRIES:
            raise ValueError("too many entries")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(json.dumps(current, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(temporary, self._path)
        self._cache = (-1, {})
        return self.overrides()


keep_alive_policy = KeepAlivePolicy(STATE_DIR / "brain" / "keep_alive.json")
