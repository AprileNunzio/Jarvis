import json
import re
import shutil
import time
import unicodedata
import uuid
from pathlib import Path

from config import STATE_DIR
from features.desktop.desk import desk

ROOT = STATE_DIR / "models3d"
MAX_BYTES = 200 * 1024 * 1024
FORMATS = {
    "glb": ("glTF binario", "web"), "gltf": ("glTF", "web"), "obj": ("Wavefront OBJ", "animazione"),
    "mtl": ("Materiali OBJ", "animazione"), "stl": ("STL", "stampa 3D"), "3mf": ("3MF", "stampa 3D"),
    "amf": ("AMF", "stampa 3D"), "ply": ("PLY (scansione)", "web"), "fbx": ("FBX", "animazione"),
    "dae": ("Collada", "animazione"), "3ds": ("3D Studio", "animazione"), "wrl": ("VRML", "web"),
    "dxf": ("DXF", "CAD"), "step": ("STEP", "CAD"), "stp": ("STEP", "CAD"), "iges": ("IGES", "CAD"),
    "igs": ("IGES", "CAD"), "brep": ("BREP", "CAD"), "dwg": ("DWG", "CAD"), "blend": ("Blender", "animazione"),
    "usd": ("USD", "web"), "usda": ("USD", "web"), "usdc": ("USD", "web"), "usdz": ("USDZ", "web"),
}
VIEWABLE = {"glb", "gltf", "obj", "stl", "3mf", "amf", "ply", "fbx", "dae", "3ds", "wrl", "dxf", "step", "stp",
            "iges", "igs", "brep"}
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,60}$")
_NAME_RE = re.compile(r"[^A-Za-z0-9._ -]+")


def slug(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")[:40] or "modello"


def safe_name(name: str) -> str:
    base = _NAME_RE.sub("_", Path(name).name).strip(" .") or "modello"
    return base[:80]


def ext_of(name: str) -> str:
    return Path(name).suffix.lower().lstrip(".")


def folder(mid: str) -> Path:
    if not _ID_RE.match(mid):
        raise KeyError(mid)
    return ROOT / mid


def _meta_path(mid: str) -> Path:
    return folder(mid) / "meta.json"


def get(mid: str) -> dict:
    try:
        return json.loads(_meta_path(mid).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise KeyError(mid)


def save_meta(meta: dict) -> dict:
    path = _meta_path(meta["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    return meta


def create(title: str, source: str, extra: dict | None = None) -> dict:
    mid = f"{slug(title)}-{uuid.uuid4().hex[:6]}"
    folder(mid).mkdir(parents=True, exist_ok=True)
    return save_meta({"id": mid, "title": title[:80], "source": source, "created": time.time(), "files": [],
                      "main": "", **(extra or {})})


def export(meta: dict) -> dict:
    from features.shares import archive
    try:
        target = archive.new_path("modelli3d", meta["title"], "modello")
        target.mkdir(parents=True, exist_ok=True)
        for f in meta["files"]:
            shutil.copy2(folder(meta["id"]) / f["name"], target / archive.dated(f["name"]))
        meta["export"] = target.name
        return save_meta(meta)
    except OSError:
        return meta


def add_file(meta: dict, name: str, data: bytes, main: bool = False) -> dict:
    if len(data) > MAX_BYTES:
        raise ValueError("File troppo grande (massimo 200 MB)")
    name = safe_name(name)
    (folder(meta["id"]) / name).write_bytes(data)
    files = [f for f in meta["files"] if f["name"] != name]
    files.append({"name": name, "format": ext_of(name), "label": FORMATS.get(ext_of(name), (ext_of(name).upper(), ""))[0],
                  "size": len(data)})
    meta["files"] = files
    if main or not meta.get("main"):
        meta["main"] = name
    return save_meta(meta)


def path(mid: str, name: str) -> Path:
    p = folder(mid) / safe_name(name)
    if not p.is_file() or p.name == "meta.json":
        raise KeyError(name)
    return p


def listing() -> list[dict]:
    if not ROOT.exists():
        return []
    out = []
    for p in ROOT.glob("*/meta.json"):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return sorted(out, key=lambda m: -m.get("created", 0))


def find(words: str) -> dict | None:
    wanted = set(slug(words).split("-")) - {"il", "la", "lo", "un", "una", "modello", "3d", "file"}
    best, score = None, 0
    for m in listing():
        s = len(wanted & set(slug(m["title"]).split("-")))
        if s > score:
            best, score = m, s
    return best


def remove(mid: str) -> None:
    shutil.rmtree(folder(mid), ignore_errors=True)


def show(meta: dict, speak: str = "") -> None:
    main = meta.get("view") or meta.get("main")
    data = {"id": meta["id"], "title": meta["title"], "main": main, "format": ext_of(main),
            "files": meta["files"], "parts": len(meta.get("parts", [])), "note": meta.get("note", ""),
            "url": f"/api/models3d/{meta['id']}/"}
    if speak:
        data.update({"announce": True, "speak": speak})
    desk.hide("viewer_3d")
    desk.show("viewer_3d", data, key=f"model:{meta['id']}", ttl=1800)
