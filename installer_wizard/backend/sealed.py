import json
import os
from pathlib import Path

from cryptography.fernet import Fernet


def write_private(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    os.replace(tmp, path)


class SealedFile:
    def __init__(self, data_path: Path, key_path: Path) -> None:
        self.data_path = data_path
        self.key_path = key_path

    def _cipher(self) -> Fernet:
        if not self.key_path.exists():
            write_private(self.key_path, Fernet.generate_key())
        return Fernet(self.key_path.read_bytes())

    def load(self) -> dict:
        if not self.data_path.exists():
            return {}
        return json.loads(self._cipher().decrypt(self.data_path.read_bytes()))

    def save(self, data: dict) -> None:
        write_private(self.data_path, self._cipher().encrypt(json.dumps(data).encode()))
