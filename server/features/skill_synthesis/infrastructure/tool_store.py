import json
import logging
import os
import tempfile
import threading
from typing import List, Optional

from server.features.skill_synthesis.domain.tool import TOOL_NAME, DynamicTool, ToolError

logger = logging.getLogger("jarvis.skill_synthesis.store")


class JsonToolStore:
    def __init__(self, directory: str) -> None:
        self._dir = directory
        self._lock = threading.Lock()
        os.makedirs(self._dir, exist_ok=True)

    def all(self) -> List[DynamicTool]:
        tools: List[DynamicTool] = []
        with self._lock:
            for entry in sorted(os.scandir(self._dir), key=lambda e: e.name):
                if not entry.name.endswith(".json") or not entry.is_file(follow_symlinks=False):
                    continue
                tool = self._read(entry.path)
                if tool is not None:
                    tools.append(tool)
        return tools

    def get(self, name: str) -> Optional[DynamicTool]:
        if not TOOL_NAME.match(name):
            return None
        with self._lock:
            return self._read(os.path.join(self._dir, f"{name}.json"))

    def save(self, tool: DynamicTool) -> None:
        tool.validate()
        payload = json.dumps(tool.to_dict(), ensure_ascii=False, indent=2)
        with self._lock:
            handle, temporary = tempfile.mkstemp(dir=self._dir, suffix=".tmp")
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(payload)
            os.replace(temporary, os.path.join(self._dir, f"{tool.name}.json"))

    def delete(self, name: str) -> bool:
        if not TOOL_NAME.match(name):
            return False
        with self._lock:
            try:
                os.unlink(os.path.join(self._dir, f"{name}.json"))
            except FileNotFoundError:
                return False
        return True

    @staticmethod
    def _read(path: str) -> Optional[DynamicTool]:
        try:
            with open(path, encoding="utf-8") as stream:
                return DynamicTool.from_dict(json.load(stream))
        except FileNotFoundError:
            return None
        except (OSError, ValueError, ToolError):
            logger.warning("ignoring unreadable tool file %s", os.path.basename(path))
            return None
