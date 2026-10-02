from features.brain.llm import BrainUnavailable, generate
from features.models3d import export, library
from features.models3d.mesh import SHAPES

SYSTEM = (
    "Sei un modellatore 3D. Descrivi l'oggetto richiesto come insieme di forme primitive e rispondi SOLO con JSON valido:\n"
    '{"title": "nome in italiano", "parts": [{"name": "nome parte", "shape": "box|cylinder|cone|sphere|torus|capsule|wedge",'
    ' "size": [larghezza, altezza, profondità], "radius": r, "height": h, "tube": t, "position": [x, y, z],'
    ' "rotation": [gradi_x, gradi_y, gradi_z], "color": "#rrggbb", "metal": true|false}]}\n'
    "Regole: misure reali in centimetri; l'asse Y è l'alto e l'oggetto poggia su y=0; box e wedge usano size, "
    "cylinder/cone/capsule usano radius e height (lungo Y), sphere usa radius, torus usa radius e tube; "
    "le parti devono toccarsi o compenetrarsi, mai fluttuare; da 3 a 40 parti; colori realistici."
)

TEMPLATES = {
    "martello": [
        {"name": "manico", "shape": "cylinder", "radius": 1.6, "height": 30, "position": [0, 15, 0], "color": "#8b5a2b"},
        {"name": "impugnatura", "shape": "cylinder", "radius": 1.9, "height": 11, "position": [0, 6, 0], "color": "#1f2933"},
        {"name": "testa", "shape": "box", "size": [11, 3.4, 3.4], "position": [1.5, 31.5, 0], "color": "#9aa4b2", "metal": True},
        {"name": "battente", "shape": "cylinder", "radius": 1.9, "height": 2.5, "position": [8, 31.5, 0], "rotation": [0, 0, 90],
         "color": "#b8c1cc", "metal": True},
        {"name": "penna", "shape": "wedge", "size": [3.4, 6, 3.4], "position": [-6.5, 31.5, 0], "rotation": [0, 0, -90],
         "color": "#9aa4b2", "metal": True},
    ],
    "tavolo": [
        {"name": "piano", "shape": "box", "size": [120, 4, 80], "position": [0, 73, 0], "color": "#a0703c"},
        *[{"name": f"gamba {i + 1}", "shape": "box", "size": [6, 71, 6], "position": [x * 54, 35.5, z * 34], "color": "#7a5230"}
          for i, (x, z) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1)))],
    ],
    "sedia": [
        {"name": "seduta", "shape": "box", "size": [44, 4, 44], "position": [0, 45, 0], "color": "#a0703c"},
        {"name": "schienale", "shape": "box", "size": [44, 40, 3], "position": [0, 67, -20.5], "color": "#a0703c"},
        *[{"name": f"gamba {i + 1}", "shape": "box", "size": [4, 43, 4], "position": [x * 19, 21.5, z * 19], "color": "#7a5230"}
          for i, (x, z) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1)))],
    ],
    "tazza": [
        {"name": "corpo", "shape": "cylinder", "radius_top": 4.2, "radius_bottom": 3.6, "height": 9.5, "position": [0, 4.75, 0], "color": "#f4f1ea"},
        {"name": "manico", "shape": "torus", "radius": 2.6, "tube": 0.55, "position": [4.6, 5, 0], "rotation": [90, 0, 0], "color": "#f4f1ea"},
    ],
    "cubo": [{"name": "cubo", "shape": "box", "size": [10, 10, 10], "position": [0, 5, 0], "color": "#29e0ff"}],
}


def _clean(parts) -> list[dict]:
    out = []
    for p in parts if isinstance(parts, list) else []:
        if isinstance(p, dict) and p.get("shape") in SHAPES:
            out.append({k: p[k] for k in ("name", "shape", "size", "radius", "radius_top", "radius_bottom", "height",
                                          "tube", "position", "rotation", "scale", "color", "metal") if k in p})
    return out[:60]


def _template(subject: str) -> list[dict] | None:
    words = library.slug(subject).split("-")
    for key, parts in TEMPLATES.items():
        if any(w.startswith(key[:5]) for w in words):
            return parts
    return None


async def design(subject: str) -> tuple[str, list[dict], str]:
    try:
        reply = await generate(f"Oggetto da modellare: {subject}", as_json=True, max_tokens=2500, temperature=0.2,
                               kind="deep", system=SYSTEM, timeout=300)
        parts = _clean(reply.get("parts")) if isinstance(reply, dict) else []
        if len(parts) >= 2:
            return str(reply.get("title") or subject)[:60], parts, "ai"
    except (BrainUnavailable, ValueError, TypeError, AttributeError):
        pass
    parts = _template(subject)
    if parts:
        return subject, parts, "template"
    raise ValueError("Il cervello non è riuscito a progettare l'oggetto")


async def create(subject: str) -> dict:
    title, parts, how = await design(subject)
    meshes = export.build(parts)
    base = library.slug(title)
    meta = library.create(title, "ai", {"parts": parts, "how": how, "prompt": subject[:200]})
    library.add_file(meta, f"{base}.glb", export.glb(meshes, title), main=True)
    library.add_file(meta, f"{base}.stl", export.stl(meshes, title))
    obj, mtl = export.obj(meshes, title, f"{base}.mtl")
    library.add_file(meta, f"{base}.obj", obj)
    meta = library.add_file(meta, f"{base}.mtl", mtl)
    meta["main"] = f"{base}.glb"
    return library.export(library.save_meta(meta))
