import os
from typing import Callable

from server.features.deep_memory.application.workspace import StructureWorkspace
from server.features.deep_memory.domain.python_extractor import SourceError
from server.features.deep_memory.domain.script_extractor import is_script

MAX_FILE_BYTES = 1024 * 1024
_REPORTED_SYMBOLS = 8


class WorkspaceError(ValueError):
    pass


class WorkspaceFiles:
    def __init__(self, root: str, structure: Callable[[], StructureWorkspace]) -> None:
        self._root = os.path.realpath(root)
        self._structure = structure

    def resolve(self, relative: str) -> str:
        if not isinstance(relative, str) or not relative.strip() or "\x00" in relative:
            raise WorkspaceError("invalid path")
        if os.path.isabs(relative) or os.path.splitdrive(relative)[0]:
            raise WorkspaceError("absolute paths are not allowed")
        full = os.path.realpath(os.path.join(self._root, relative))
        if os.path.commonpath([self._root, full]) != self._root or full == self._root:
            raise WorkspaceError("path traversal detected")
        return full

    def make_directory(self, relative: str) -> str:
        os.makedirs(self.resolve(relative), exist_ok=True)
        return f"Directory {relative} creata con successo."

    def write(self, relative: str, content: str) -> str:
        if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise WorkspaceError("content must be text of at most 1 MB")
        full = self.resolve(relative)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        return f"File {relative} scritto con successo.{self._track(self._normalise(relative), content)}"

    def _normalise(self, relative: str) -> str:
        return os.path.relpath(self.resolve(relative), self._root).replace(os.sep, "/")

    def _track(self, relative: str, content: str) -> str:
        if not (relative.endswith(".py") or is_script(relative)):
            return ""
        try:
            invalidation = self._structure().update_file(relative, content)
        except SourceError as exc:
            return f" Attenzione, il file non è analizzabile: {exc}."
        if not invalidation.invalidated:
            return ""
        others = sorted(invalidation.invalidated - invalidation.changed)
        shown = ", ".join(others[:_REPORTED_SYMBOLS]) + ("…" if len(others) > _REPORTED_SYMBOLS else "")
        return f" Questa modifica invalida {len(others)} elementi che ne dipendono ({shown}): verificali." if others else ""
