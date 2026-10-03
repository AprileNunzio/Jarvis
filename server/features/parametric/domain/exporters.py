from typing import List, Sequence, Tuple

from server.features.parametric.domain.geometry import Mesh
from server.features.parametric.domain.schema import (
    BoxPart,
    ConePart,
    CylinderPart,
    GableRoofPart,
    ModelSpec,
    SpherePart,
)

NamedMesh = Tuple[str, str, Mesh]


def _num(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def to_obj(model_name: str, meshes: Sequence[NamedMesh]) -> str:
    lines: List[str] = [f"# {model_name}", "# up axis: Y, source model up axis: Z"]
    offset = 0
    for name, _, mesh in meshes:
        lines.append(f"o {name}")
        for x, y, z in mesh.vertices:
            lines.append(f"v {_num(x)} {_num(z)} {_num(-y)}")
        for face in mesh.faces:
            lines.append("f " + " ".join(str(i + 1 + offset) for i in face))
        offset += len(mesh.vertices)
    return "\n".join(lines) + "\n"


def _face_entity(layer: str, points: Sequence[Tuple[float, float, float]]) -> List[str]:
    quad = list(points) + [points[-1]] * (4 - len(points))
    lines = ["0", "3DFACE", "8", layer]
    for index, (x, y, z) in enumerate(quad):
        lines += [str(10 + index), _num(x), str(20 + index), _num(y), str(30 + index), _num(z)]
    return lines


def to_dxf(meshes: Sequence[NamedMesh]) -> str:
    lines: List[str] = ["0", "SECTION", "2", "ENTITIES"]
    for _, layer, mesh in meshes:
        for face in mesh.faces:
            corners = [mesh.vertices[i] for i in face]
            if len(corners) == 3 or len(corners) == 4:
                lines += _face_entity(layer, corners)
            else:
                for k in range(1, len(corners) - 1):
                    lines += _face_entity(layer, [corners[0], corners[k], corners[k + 1]])
    lines += ["0", "ENDSEC", "0", "EOF"]
    return "\n".join(lines) + "\n"


def _point(x: float, y: float, z: float) -> str:
    return f"(list {_num(x)} {_num(y)} {_num(z)})"


def _lisp_for(part) -> List[str]:
    px, py, pz = part.position
    lift = 0.0
    commands: List[str] = []
    if isinstance(part, BoxPart):
        sx, sy, sz = part.size
        lift = -sz / 2 if part.anchor == "center" else 0.0
        commands.append(f'(command "_.BOX" "_C" {_point(px, py, pz + lift + sz / 2)} "_L" {_num(sx)} {_num(sy)} {_num(sz)})')
    elif isinstance(part, CylinderPart):
        lift = -part.height / 2 if part.anchor == "center" else 0.0
        commands.append(f'(command "_.CYLINDER" {_point(px, py, pz + lift)} {_num(part.radius)} {_num(part.height)})')
    elif isinstance(part, ConePart):
        lift = -part.height / 2 if part.anchor == "center" else 0.0
        commands.append(f'(command "_.CONE" {_point(px, py, pz + lift)} {_num(part.radius)} {_num(part.height)})')
    elif isinstance(part, SpherePart):
        lift = -part.radius if part.anchor == "center" else 0.0
        commands.append(f'(command "_.SPHERE" {_point(px, py, pz + lift + part.radius)} {_num(part.radius)})')
    elif isinstance(part, GableRoofPart):
        commands.append(f";; gable_roof {part.name} is exported in the DXF and OBJ files only")
        return commands
    for axis, angle in zip(("_X", "_Y", "_Z"), part.rotation_deg):
        if angle:
            commands.append(f'(command "_.ROTATE3D" (entlast) "" "{axis}" {_point(px, py, pz)} {_num(angle)})')
    if part.layer != "0":
        commands.append(f'(command "_.CHPROP" (entlast) "" "_LA" "{part.layer}" "")')
    return commands


def to_autolisp(spec: ModelSpec) -> str:
    lines = [f";; {spec.name} ({spec.units})", f"(defun c:build-{spec.name} ()", '  (setvar "CMDECHO" 0)']
    lines += [f"  {command}" for part in spec.parts for command in _lisp_for(part)]
    lines += ["  (princ))", f"(c:build-{spec.name})"]
    return "\n".join(lines) + "\n"
