import hashlib
import os
import re
import time
from pathlib import Path
from typing import Optional

NAME = re.compile(r"^[0-9a-f]{24}\.png$")
MAX_FILES = 150
MAX_AGE_SECONDS = 14 * 86400


class ImageStore:
    def __init__(self, directory: Path) -> None:
        self._dir = directory

    def save(self, png: bytes) -> str:
        name = hashlib.sha256(png).hexdigest()[:24] + ".png"
        self._dir.mkdir(parents=True, exist_ok=True)
        target = self._dir / name
        if not target.exists():
            temporary = target.with_suffix(".tmp")
            temporary.write_bytes(png)
            os.replace(temporary, target)
        self._prune()
        return name

    def path(self, name: str) -> Optional[Path]:
        if not NAME.match(name or ""):
            return None
        target = self._dir / name
        return target if target.is_file() else None

    def _prune(self) -> None:
        files = sorted((p for p in self._dir.glob("*.png")), key=lambda p: p.stat().st_mtime, reverse=True)
        limit = time.time() - MAX_AGE_SECONDS
        for index, path in enumerate(files):
            if index >= MAX_FILES or path.stat().st_mtime < limit:
                path.unlink(missing_ok=True)
