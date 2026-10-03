from dataclasses import dataclass
from typing import Dict, List, Tuple

from server.features.parametric.domain.exporters import NamedMesh, to_autolisp, to_dxf, to_obj
from server.features.parametric.domain.geometry import build_part
from server.features.parametric.domain.schema import ModelSpec


@dataclass(frozen=True)
class RenderedModel:
    files: Dict[str, str]
    vertices: int
    faces: int
    bounds: Tuple[Tuple[float, float, float], Tuple[float, float, float]]


def render(spec: ModelSpec) -> RenderedModel:
    meshes: List[NamedMesh] = [(part.name, part.layer, build_part(part)) for part in spec.parts]
    points = [v for _, _, mesh in meshes for v in mesh.vertices]
    lower = tuple(min(p[i] for p in points) for i in range(3))
    upper = tuple(max(p[i] for p in points) for i in range(3))
    return RenderedModel(
        files={
            f"{spec.name}.obj": to_obj(spec.name, meshes),
            f"{spec.name}.dxf": to_dxf(meshes),
            f"{spec.name}.lsp": to_autolisp(spec),
        },
        vertices=len(points),
        faces=sum(len(mesh.faces) for _, _, mesh in meshes),
        bounds=(lower, upper),
    )
