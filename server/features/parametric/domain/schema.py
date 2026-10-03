import math
from typing import Annotated, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_PARTS = 400
MAX_ABS_COORDINATE = 100000.0
MAX_SEGMENTS = 96
_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$"

Vector = Tuple[float, float, float]


def _finite_bounded(values: Vector) -> Vector:
    for value in values:
        if not math.isfinite(value) or abs(value) > MAX_ABS_COORDINATE:
            raise ValueError(f"value {value} is not a finite number within +-{MAX_ABS_COORDINATE:g}")
    return values


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _PartBase(_Strict):
    name: str = Field(pattern=_IDENTIFIER)
    layer: str = Field(default="0", pattern=_IDENTIFIER)
    position: Vector = (0.0, 0.0, 0.0)
    rotation_deg: Vector = (0.0, 0.0, 0.0)
    anchor: Literal["base", "center"] = "base"

    @field_validator("position", "rotation_deg")
    @classmethod
    def _check_vector(cls, value: Vector) -> Vector:
        return _finite_bounded(value)


def _positive(value: float) -> float:
    if not math.isfinite(value) or not 0 < value <= MAX_ABS_COORDINATE:
        raise ValueError("dimension must be a finite number greater than 0")
    return value


class BoxPart(_PartBase):
    shape: Literal["box"]
    size: Vector

    @field_validator("size")
    @classmethod
    def _check_size(cls, value: Vector) -> Vector:
        for v in value:
            _positive(v)
        return value


class CylinderPart(_PartBase):
    shape: Literal["cylinder"]
    radius: float
    height: float
    segments: int = Field(default=24, ge=3, le=MAX_SEGMENTS)

    @field_validator("radius", "height")
    @classmethod
    def _check_dimension(cls, value: float) -> float:
        return _positive(value)


class ConePart(_PartBase):
    shape: Literal["cone"]
    radius: float
    height: float
    segments: int = Field(default=24, ge=3, le=MAX_SEGMENTS)

    @field_validator("radius", "height")
    @classmethod
    def _check_dimension(cls, value: float) -> float:
        return _positive(value)


class SpherePart(_PartBase):
    shape: Literal["sphere"]
    radius: float
    segments: int = Field(default=16, ge=4, le=MAX_SEGMENTS)

    @field_validator("radius")
    @classmethod
    def _check_dimension(cls, value: float) -> float:
        return _positive(value)


class GableRoofPart(_PartBase):
    shape: Literal["gable_roof"]
    width: float
    depth: float
    height: float

    @field_validator("width", "depth", "height")
    @classmethod
    def _check_dimension(cls, value: float) -> float:
        return _positive(value)


Part = Annotated[Union[BoxPart, CylinderPart, ConePart, SpherePart, GableRoofPart], Field(discriminator="shape")]


class ModelSpec(_Strict):
    name: str = Field(pattern=_IDENTIFIER)
    units: Literal["mm", "cm", "m"] = "m"
    parts: List[Part] = Field(min_length=1, max_length=MAX_PARTS)

    @model_validator(mode="after")
    def _unique_names(self) -> "ModelSpec":
        names = [p.name for p in self.parts]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ValueError(f"duplicate part names: {duplicates}")
        return self


def spec_prompt_description() -> str:
    return (
        "Schema JSON obbligatorio (nessun campo extra, numeri finiti, dimensioni > 0, unità: units):\n"
        '{"name": "id", "units": "mm|cm|m", "parts": [ PART, ... ]}\n'
        "PART comune: name (id univoco), layer (id, default \"0\"), position [x,y,z], rotation_deg [rx,ry,rz], "
        'anchor ("base" = position è il centro della faccia inferiore, "center" = centro del volume). Asse verticale: z.\n'
        'shape "box": size [x,y,z]\n'
        'shape "cylinder": radius, height, segments (3-96)\n'
        'shape "cone": radius, height, segments\n'
        'shape "sphere": radius, segments (4-96)\n'
        'shape "gable_roof": width (x), depth (y), height (colmo lungo x)\n'
        f"Massimo {MAX_PARTS} parti. Rispondi SOLO con il JSON."
    )


def first_error_lines(error: Exception, limit: int = 6) -> Optional[str]:
    errors = getattr(error, "errors", None)
    if errors is None:
        return str(error)
    lines = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in errors()[:limit]]
    return "; ".join(lines)
