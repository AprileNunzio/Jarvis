import base64
import json
import math
from dataclasses import dataclass
from typing import List

MAX_FILE_BYTES = 8 * 1024 * 1024
_COMPONENT_BYTES = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
_TYPE_COUNTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}


@dataclass(frozen=True)
class FormatReport:
    problems: List[str]
    vertices: int = 0
    faces: int = 0

    @property
    def valid(self) -> bool:
        return not self.problems


def check_obj(text: str) -> FormatReport:
    problems: List[str] = []
    vertices = 0
    faces: List[List[str]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        keyword, args = parts[0], parts[1:]
        if keyword == "v":
            if len(args) not in (3, 4) or not _all_finite(args):
                problems.append(f"line {number}: invalid vertex")
            vertices += 1
        elif keyword in ("vn", "vt"):
            if not args or not _all_finite(args):
                problems.append(f"line {number}: invalid {keyword}")
        elif keyword == "f":
            if len(args) < 3:
                problems.append(f"line {number}: face needs at least 3 vertices")
            faces.append(args)
    for index, face in enumerate(faces, start=1):
        for token in face:
            ref = token.split("/")[0]
            try:
                position = int(ref)
            except ValueError:
                problems.append(f"face {index}: non-numeric index {token!r}")
                continue
            if position == 0 or abs(position) > vertices:
                problems.append(f"face {index}: vertex index {position} outside 1..{vertices}")
    if vertices == 0:
        problems.append("no vertices")
    if not faces:
        problems.append("no faces")
    return FormatReport(problems[:20], vertices, len(faces))


def _all_finite(values: List[str]) -> bool:
    try:
        return all(math.isfinite(float(v)) for v in values)
    except ValueError:
        return False


def check_gltf(text: str) -> FormatReport:
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return FormatReport([f"invalid JSON: {exc.msg}"])
    if not isinstance(doc, dict):
        return FormatReport(["root must be an object"])
    problems: List[str] = []
    if doc.get("asset", {}).get("version") != "2.0":
        problems.append("asset.version must be 2.0")
    buffers, views = doc.get("buffers", []), doc.get("bufferViews", [])
    accessors, meshes = doc.get("accessors", []), doc.get("meshes", [])
    if not meshes:
        problems.append("no meshes")
    _check_buffers(buffers, problems)
    _check_views(views, buffers, problems)
    _check_accessors(accessors, views, problems)
    faces = _check_meshes(meshes, accessors, problems)
    return FormatReport(problems[:20], faces=faces)


def _check_buffers(buffers: list, problems: List[str]) -> None:
    for i, buf in enumerate(buffers):
        uri = buf.get("uri", "")
        if uri.startswith("data:"):
            try:
                size = len(base64.b64decode(uri.split(",", 1)[1], validate=True))
            except (IndexError, ValueError):
                problems.append(f"buffer {i}: invalid data URI")
                continue
            if size != buf.get("byteLength"):
                problems.append(f"buffer {i}: byteLength {buf.get('byteLength')} != {size}")


def _check_views(views: list, buffers: list, problems: List[str]) -> None:
    for i, view in enumerate(views):
        index = view.get("buffer", -1)
        if not 0 <= index < len(buffers):
            problems.append(f"bufferView {i}: buffer {index} out of range")
        elif view.get("byteOffset", 0) + view.get("byteLength", 0) > buffers[index].get("byteLength", 0):
            problems.append(f"bufferView {i}: exceeds buffer {index}")


def _check_accessors(accessors: list, views: list, problems: List[str]) -> None:
    for i, acc in enumerate(accessors):
        view_index = acc.get("bufferView", -1)
        if not 0 <= view_index < len(views):
            problems.append(f"accessor {i}: bufferView {view_index} out of range")
            continue
        size = _COMPONENT_BYTES.get(acc.get("componentType"))
        width = _TYPE_COUNTS.get(acc.get("type"))
        if size is None or width is None:
            problems.append(f"accessor {i}: unknown componentType or type")
            continue
        needed = acc.get("byteOffset", 0) + acc.get("count", 0) * size * width
        if needed > views[view_index].get("byteLength", 0):
            problems.append(f"accessor {i}: needs {needed} bytes, view has {views[view_index].get('byteLength', 0)}")


def _check_meshes(meshes: list, accessors: list, problems: List[str]) -> int:
    triangles = 0
    for i, mesh in enumerate(meshes):
        primitives = mesh.get("primitives", [])
        if not primitives:
            problems.append(f"mesh {i}: no primitives")
        for j, prim in enumerate(primitives):
            position = prim.get("attributes", {}).get("POSITION", -1)
            if not 0 <= position < len(accessors):
                problems.append(f"mesh {i} primitive {j}: POSITION accessor {position} out of range")
                continue
            index = prim.get("indices")
            if index is not None and not 0 <= index < len(accessors):
                problems.append(f"mesh {i} primitive {j}: indices accessor {index} out of range")
            elif index is not None:
                triangles += accessors[index].get("count", 0) // 3
    return triangles


def check_dxf(text: str) -> FormatReport:
    lines = [line.strip() for line in text.splitlines()]
    problems: List[str] = []
    if len(lines) % 2:
        problems.append("odd number of lines: group codes and values must pair up")
    pairs = list(zip(lines[0::2], lines[1::2]))
    for number, (code, _) in enumerate(pairs, start=1):
        if not code.lstrip("-").isdigit():
            problems.append(f"pair {number}: invalid group code {code!r}")
            break
    if pairs and pairs[-1] != ("0", "EOF"):
        problems.append("missing EOF marker")
    if ("0", "SECTION") not in pairs or ("2", "ENTITIES") not in pairs:
        problems.append("missing ENTITIES section")
    faces = sum(1 for pair in pairs if pair == ("0", "3DFACE"))
    for index, (code, value) in enumerate(pairs):
        if code in {str(c) for c in (10, 11, 12, 13, 20, 21, 22, 23, 30, 31, 32, 33)} and not _all_finite([value]):
            problems.append(f"pair {index + 1}: invalid coordinate {value!r}")
            break
    if faces == 0:
        problems.append("no 3DFACE entities")
    return FormatReport(problems[:20], faces=faces)


def check_autolisp(text: str) -> FormatReport:
    depth, in_string, in_comment, line = 0, False, False, 1
    problems: List[str] = []
    for char in text:
        if char == "\n":
            line += 1
            in_comment = False
        elif in_comment:
            continue
        elif char == '"':
            in_string = not in_string
        elif in_string:
            continue
        elif char == ";":
            in_comment = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                problems.append(f"line {line}: unbalanced closing parenthesis")
                break
    if in_string:
        problems.append("unterminated string")
    if depth > 0:
        problems.append(f"{depth} unclosed parentheses")
    if not text.strip():
        problems.append("empty script")
    return FormatReport(problems)
