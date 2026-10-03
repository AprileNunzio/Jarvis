import struct
from dataclasses import dataclass, field

MIN_SIDE = 4
MAX_AREA_SHARE = 0.85

UI_PROMPT = (
    "Questo è lo screenshot di uno schermo largo {width} e alto {height} pixel. Trova l'elemento dell'interfaccia "
    "descritto così: «{query}». {avoid}Rispondi SOLO con JSON: {{\"found\": true o false, \"elements\": "
    "[{{\"label\": testo o nome dell'elemento, \"box\": [x, y, larghezza, altezza] con valori normalizzati tra 0 e 1 "
    "rispetto all'intera immagine, \"confidence\": numero tra 0 e 1}}]}}. Elenca al massimo 3 candidati, il più "
    "probabile per primo. Se l'elemento non c'è, found=false e elements vuoto."
)


@dataclass(frozen=True)
class UiElement:
    label: str
    x: int
    y: int
    width: int
    height: int
    confidence: float

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.width // 2, self.y + self.height // 2

    @property
    def box(self) -> list[int]:
        return [self.x, self.y, self.width, self.height]

    def to_dict(self) -> dict:
        cx, cy = self.center
        return {"label": self.label, "x": self.x, "y": self.y, "width": self.width, "height": self.height,
                "cx": cx, "cy": cy, "confidence": round(self.confidence, 3)}


@dataclass(frozen=True)
class Screen:
    width: int
    height: int
    failed_points: tuple = field(default_factory=tuple)


def image_size(data: bytes) -> tuple[int, int]:
    if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        width, height = struct.unpack(">II", data[16:24])
        return width, height
    raise ValueError("lo screenshot non è un PNG valido")


def prompt_for(query: str, screen: Screen) -> str:
    avoid = ""
    if screen.failed_points:
        points = ", ".join(f"({x}, {y})" for x, y in screen.failed_points[-3:])
        avoid = f"I clic già provati nei punti {points} non hanno avuto effetto: scegli un elemento diverso o più preciso. "
    return UI_PROMPT.format(width=screen.width, height=screen.height, query=query.replace("{", "(").replace("}", ")"), avoid=avoid)


def parse_elements(data, screen: Screen) -> list[UiElement]:
    if not isinstance(data, dict) or data.get("found") is False:
        return []
    found: list[UiElement] = []
    for item in data.get("elements") or []:
        element = _element(item, screen)
        if element is not None:
            found.append(element)
    return sorted(found, key=lambda e: e.confidence, reverse=True)[:3]


def _element(item, screen: Screen) -> UiElement | None:
    try:
        nx, ny, nw, nh = (float(v) for v in item["box"])
        confidence = min(max(float(item.get("confidence", 0.5)), 0.0), 1.0)
    except (KeyError, TypeError, ValueError):
        return None
    if not all(0.0 <= v <= 1.0 for v in (nx, ny, nw, nh)):
        return None
    x, y = round(nx * screen.width), round(ny * screen.height)
    width, height = round(nw * screen.width), round(nh * screen.height)
    x2, y2 = min(x + width, screen.width), min(y + height, screen.height)
    width, height = x2 - x, y2 - y
    if width < MIN_SIDE or height < MIN_SIDE or width * height > MAX_AREA_SHARE * screen.width * screen.height:
        return None
    return UiElement(str(item.get("label", ""))[:80], x, y, width, height, confidence)
