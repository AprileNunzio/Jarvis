import math
from dataclasses import dataclass
from typing import List, Tuple

from server.features.parametric.domain.schema import (
    BoxPart,
    ConePart,
    CylinderPart,
    GableRoofPart,
    SpherePart,
    Vector,
)

Point = Tuple[float, float, float]


@dataclass(frozen=True)
class Mesh:
    vertices: Tuple[Point, ...]
    faces: Tuple[Tuple[int, ...], ...]


def _box(sx: float, sy: float, sz: float) -> Mesh:
    x, y = sx / 2, sy / 2
    v = ((-x, -y, 0), (x, -y, 0), (x, y, 0), (-x, y, 0), (-x, -y, sz), (x, -y, sz), (x, y, sz), (-x, y, sz))
    f = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))
    return Mesh(v, f)


def _ring(radius: float, z: float, segments: int) -> List[Point]:
    return [(radius * math.cos(2 * math.pi * i / segments), radius * math.sin(2 * math.pi * i / segments), z) for i in range(segments)]


def _cylinder(radius: float, height: float, segments: int) -> Mesh:
    vertices = _ring(radius, 0.0, segments) + _ring(radius, height, segments)
    faces = [tuple(reversed(range(segments))), tuple(range(segments, 2 * segments))]
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((i, j, segments + j, segments + i))
    return Mesh(tuple(vertices), tuple(faces))


def _cone(radius: float, height: float, segments: int) -> Mesh:
    vertices = _ring(radius, 0.0, segments) + [(0.0, 0.0, height)]
    apex = segments
    faces = [tuple(reversed(range(segments)))] + [(i, (i + 1) % segments, apex) for i in range(segments)]
    return Mesh(tuple(vertices), tuple(faces))


def _sphere(radius: float, segments: int) -> Mesh:
    rings = max(segments // 2, 2)
    vertices: List[Point] = [(0.0, 0.0, 0.0)]
    for r in range(1, rings):
        phi = math.pi * r / rings
        vertices += _ring(radius * math.sin(phi), radius - radius * math.cos(phi), segments)
    vertices.append((0.0, 0.0, 2 * radius))
    top = len(vertices) - 1
    faces: List[Tuple[int, ...]] = []
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((0, 1 + j, 1 + i))
        for r in range(rings - 2):
            a, b = 1 + r * segments, 1 + (r + 1) * segments
            faces.append((a + i, a + j, b + j, b + i))
        last = 1 + (rings - 2) * segments
        faces.append((last + i, last + j, top))
    return Mesh(tuple(vertices), tuple(faces))


def _gable_roof(width: float, depth: float, height: float) -> Mesh:
    x, y = width / 2, depth / 2
    v = ((-x, -y, 0), (x, -y, 0), (x, y, 0), (-x, y, 0), (-x, 0, height), (x, 0, height))
    f = ((0, 3, 2, 1), (0, 1, 5, 4), (3, 4, 5, 2), (0, 4, 3), (1, 2, 5))
    return Mesh(v, f)


def _rotate(point: Point, rotation_deg: Vector) -> Point:
    x, y, z = point
    rx, ry, rz = (math.radians(a) for a in rotation_deg)
    y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
    x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
    x, y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)
    return (x, y, z)


def _height(part) -> float:
    if isinstance(part, BoxPart):
        return part.size[2]
    if isinstance(part, SpherePart):
        return 2 * part.radius
    return part.height


def build_part(part) -> Mesh:
    if isinstance(part, BoxPart):
        local = _box(*part.size)
    elif isinstance(part, CylinderPart):
        local = _cylinder(part.radius, part.height, part.segments)
    elif isinstance(part, ConePart):
        local = _cone(part.radius, part.height, part.segments)
    elif isinstance(part, SpherePart):
        local = _sphere(part.radius, part.segments)
    elif isinstance(part, GableRoofPart):
        local = _gable_roof(part.width, part.depth, part.height)
    else:
        raise TypeError(f"unsupported part {type(part).__name__}")
    lift = -_height(part) / 2 if part.anchor == "center" else 0.0
    px, py, pz = part.position
    placed = []
    for vx, vy, vz in local.vertices:
        rx, ry, rz = _rotate((vx, vy, vz + lift), part.rotation_deg)
        placed.append((rx + px, ry + py, rz + pz))
    return Mesh(tuple(placed), local.faces)
