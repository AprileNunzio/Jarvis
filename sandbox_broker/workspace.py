import os
import shutil
import stat
import tempfile
from typing import Optional

from sandbox_broker.docker_cmd import entrypoint_name
from server.features.sandbox.domain.spec import ExecutionSpec


class Workspace:
    def __init__(self, root: str, spec: ExecutionSpec, owner_uid: Optional[int]) -> None:
        self._root = root
        self._spec = spec
        self._uid = owner_uid
        self.path = ""
        self.in_dir = ""
        self.out_dir = ""

    def __enter__(self) -> "Workspace":
        os.makedirs(self._root, mode=0o755, exist_ok=True)
        self.path = tempfile.mkdtemp(prefix="job-", dir=self._root)
        os.chmod(self.path, 0o755)
        self.in_dir = os.path.join(self.path, "in")
        self.out_dir = os.path.join(self.path, "out")
        os.mkdir(self.in_dir, 0o755)
        os.mkdir(self.out_dir, 0o700)
        self._write(entrypoint_name(self._spec.language), self._spec.source.encode("utf-8"))
        for name, content in self._spec.inputs.items():
            self._write(name, content)
        os.chmod(self.in_dir, 0o555)
        self._hand_out_dir()
        return self

    def __exit__(self, *exc) -> None:
        shutil.rmtree(self.path, onerror=_make_writable_and_retry)

    def _write(self, name: str, content: bytes) -> None:
        target = os.path.join(self.in_dir, name)
        with open(target, "wb") as handle:
            handle.write(content)
        os.chmod(target, 0o444)

    def _hand_out_dir(self) -> None:
        if self._uid is not None and hasattr(os, "chown"):
            os.chown(self.out_dir, self._uid, self._uid)


def _make_writable_and_retry(function, path, _excinfo) -> None:
    parent = os.path.dirname(path)
    os.chmod(parent, stat.S_IRWXU)
    os.chmod(path, stat.S_IRWXU)
    function(path)
