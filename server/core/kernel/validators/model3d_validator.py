from typing import Callable, Dict

from server.core.kernel.domain.node import NodeSpec
from server.core.kernel.domain.outcome import NodeResult, Verdict
from server.core.kernel.validators.model3d_formats import MAX_FILE_BYTES, FormatReport, check_gltf, check_obj

_CHECKERS: Dict[str, Callable[[str], FormatReport]] = {".obj": check_obj, ".gltf": check_gltf}


class Model3DArtifactValidator:
    def __init__(self, require_model: bool = False) -> None:
        self._require_model = require_model

    async def judge(self, node: NodeSpec, result: NodeResult) -> Verdict:
        files = result.output.get("files") or {}
        if not isinstance(files, dict):
            return Verdict.reject("invalid_artifact", "files must be a mapping of name to content")
        checked = 0
        for name, content in files.items():
            extension = _extension(name)
            if extension not in _CHECKERS:
                continue
            checked += 1
            if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_FILE_BYTES:
                return Verdict.reject("invalid_artifact", f"{name}: content missing or too large")
            report = _CHECKERS[extension](content)
            if not report.valid:
                return Verdict.reject("model_syntax", f"{name}: " + "; ".join(report.problems[:5]), file=name, problems=report.problems)
        if self._require_model and checked == 0:
            return Verdict.reject("missing_artifact", "no .obj or .gltf file was produced")
        return Verdict.accept()


def _extension(name: str) -> str:
    dot = name.rfind(".")
    return name[dot:].lower() if dot != -1 else ""
