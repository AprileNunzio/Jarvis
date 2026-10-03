import os
import re
from dataclasses import dataclass
from typing import Dict, Optional

from server.features.parametric.application.translator import SpecTranslator
from server.features.parametric.domain.renderer import RenderedModel, render
from server.features.parametric.domain.schema import ModelSpec

_SAFE_FOLDER = re.compile(r"[^A-Za-z0-9_-]")


@dataclass(frozen=True)
class DesignResult:
    spec: ModelSpec
    rendered: RenderedModel
    attempts: int
    folder: str
    written: Dict[str, str]


class ParametricDesigner:
    def __init__(self, translator: SpecTranslator, output_root: str) -> None:
        self._translator = translator
        self._root = output_root

    async def design(self, intent: str, job_id: str, hint: Optional[str] = None) -> DesignResult:
        translated = await self._translator.translate(intent, hint)
        rendered = render(translated.spec)
        folder = os.path.join(self._root, _SAFE_FOLDER.sub("_", job_id)[:64] or "job")
        return DesignResult(translated.spec, rendered, translated.attempts, folder, self._write(folder, rendered))

    @staticmethod
    def _write(folder: str, rendered: RenderedModel) -> Dict[str, str]:
        os.makedirs(folder, exist_ok=True)
        written: Dict[str, str] = {}
        for name, content in rendered.files.items():
            target = os.path.join(folder, name)
            with open(target, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
            written[name] = target
        return written
