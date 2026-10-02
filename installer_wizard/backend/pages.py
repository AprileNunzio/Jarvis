import json
import re
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from access import NO_CACHE
from config import FEATURES_DIR, JARVIS_DIR, STATE_DIR, WEB_DIR, read_env

VENDOR_DIR = STATE_DIR / "vendor"
VENDOR = {
    "three.min.js": "https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js",
    "OrbitControls.js": "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js",
    "GLTFLoader.js": "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js",
    "head.glb": "https://cdn.jsdelivr.net/gh/mrdoob/three.js@r128/examples/models/gltf/LeePerrySmith/LeePerrySmith.glb",
    "face-color.jpg": "https://cdn.jsdelivr.net/gh/mrdoob/three.js@r128/examples/models/gltf/LeePerrySmith/Map-COL.jpg",
    "face-spec.jpg": "https://cdn.jsdelivr.net/gh/mrdoob/three.js@r128/examples/models/gltf/LeePerrySmith/Map-SPEC.jpg",
    "face-normal.jpg": "https://cdn.jsdelivr.net/gh/mrdoob/three.js@r128/examples/models/gltf/LeePerrySmith/Infinite-Level_02_Tangent_SmoothUV.jpg",
    **{f"{n}.js": f"https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/{n}.js"
       for n in ("OBJLoader", "MTLLoader", "STLLoader", "PLYLoader", "FBXLoader", "ColladaLoader", "3MFLoader",
                 "AMFLoader", "TDSLoader", "VRMLLoader")},
    **{f"{n}.js": f"https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/{d}/{n}.js"
       for d, n in (("libs", "fflate.min"), ("libs", "chevrotain.min"), ("curves", "NURBSCurve"), ("curves", "NURBSUtils"))},
    "occt-import-js.js": "https://cdn.jsdelivr.net/npm/occt-import-js@0.0.22/dist/occt-import-js.js",
    "occt-import-js.wasm": "https://cdn.jsdelivr.net/npm/occt-import-js@0.0.22/dist/occt-import-js.wasm",
    "vision_bundle.mjs": "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs",
    "vision_wasm_internal.js": "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm/vision_wasm_internal.js",
    "vision_wasm_internal.wasm": "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm/vision_wasm_internal.wasm",
    "leaflet.js": "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js",
    "leaflet.css": "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css",
    "hand_landmarker.task": "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
}
ADMIN_ASSET_RE = re.compile(r"^admin(-[a-z]{2,20})?\.(js|css)$")
ADMIN_TYPES = {"js": "application/javascript", "css": "text/css"}
_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_ASSET_RE = re.compile(r'((?:src|href)="/(?:static|vendor|features)/[^"?]+)"')


def _asset_version() -> str:
    try:
        head = (JARVIS_DIR / ".git" / "HEAD").read_text().strip()
        if head.startswith("ref:"):
            head = (JARVIS_DIR / ".git" / head[5:]).read_text().strip()
        return head[:10]
    except OSError:
        return str(int(time.time()))


ASSET_VERSION = _asset_version()


def face_options() -> dict:
    env = read_env()

    def color(key, default):
        value = env.get(key, "")
        return value if _COLOR_RE.match(value) else default

    def choice(key, options, default):
        value = env.get(key, default)
        return value if value in options else default

    hands = choice("JARVIS_HANDS", ("auto", "1", "0"), "auto")
    return {"avatar": choice("JARVIS_AVATAR", ("auto", "full", "light"), "auto"),
            "style": "hologram", "color": color("JARVIS_FACE_COLOR", "#29e0ff"),
            "hands": "0" if env.get("JARVIS_VISION", "1") == "0" else hands,
            "hands_fps": int(choice("JARVIS_HANDS_FPS", ("10", "20", "30"), "20")),
            "hands_count": int(choice("JARVIS_HANDS_COUNT", ("1", "2"), "2")),
            "hands_max_ms": int(choice("JARVIS_HANDS_MAX_MS", ("30", "50", "90"), "50"))}


def _assets(folder: Path, ext: str) -> list[str]:
    names = [p.name for p in folder.glob(f"admin*.{ext}") if ADMIN_ASSET_RE.match(p.name)]
    return sorted(names, key=lambda n: (n != f"admin.{ext}", n))


def admin_parts() -> dict[str, str]:
    parts = {"feature-styles": [], "feature-tabs": [], "feature-scripts": []}
    for folder in sorted(p for p in FEATURES_DIR.iterdir() if p.is_dir()):
        for css in _assets(folder, "css"):
            parts["feature-styles"].append(f'<link rel="stylesheet" href="/features/{folder.name}/{css}">')
        if (folder / "admin.html").exists():
            parts["feature-tabs"].append((folder / "admin.html").read_text(encoding="utf-8"))
        for js in _assets(folder, "js"):
            parts["feature-scripts"].append(f'<script src="/features/{folder.name}/{js}"></script>')
    return {k: "\n".join(v) for k, v in parts.items()}


def render(html: str) -> Response:
    html = html.replace("</head>", f"<script>window.JARVIS_FACE = {json.dumps(face_options())}; "
                                   f"window.JARVIS_ASSET_V = {json.dumps(ASSET_VERSION)};</script>\n</head>", 1)
    html = _ASSET_RE.sub(lambda m: f'{m.group(1)}?v={ASSET_VERSION}"', html)
    return Response(html, media_type="text/html", headers=NO_CACHE)


def page(name: str) -> Response:
    html = (WEB_DIR / name).read_text(encoding="utf-8")
    if "<jarvis-slot" in html:
        for key, value in admin_parts().items():
            html = html.replace(f'<jarvis-slot name="{key}"></jarvis-slot>', value)
    return render(html)


class FreshStatic(StaticFiles):

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


def mount_static(app: FastAPI, *components: str) -> None:
    for component in components:
        app.mount(f"/static/{component}", FreshStatic(directory=WEB_DIR / component), name=f"static-{component}")


public_routes = APIRouter()
admin_routes = APIRouter()


@public_routes.get("/vendor/{name}")
async def vendor(name: str):
    if name not in VENDOR:
        raise HTTPException(404, "Risorsa sconosciuta")
    path = VENDOR_DIR / name
    if not path.exists():
        try:
            async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
                r = await client.get(VENDOR[name])
                r.raise_for_status()
            VENDOR_DIR.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".part")
            tmp.write_bytes(r.content)
            tmp.replace(path)
        except httpx.HTTPError:
            raise HTTPException(502, "Risorsa non disponibile")
    media = ("model/gltf-binary" if name.endswith(".glb") else "image/jpeg" if name.endswith(".jpg")
             else "application/wasm" if name.endswith(".wasm") else "application/octet-stream" if name.endswith(".task")
             else "text/css" if name.endswith(".css")
             else "application/javascript")
    return FileResponse(path, media_type=media, headers={"Cache-Control": "public, max-age=604800"})


@admin_routes.get("/features/{fid}/{name}")
async def feature_asset(fid: str, name: str):
    path = FEATURES_DIR / fid / name
    match = ADMIN_ASSET_RE.match(name)
    if not match or not fid.isidentifier() or not path.is_file():
        raise HTTPException(404, "Risorsa sconosciuta")
    return FileResponse(path, media_type=ADMIN_TYPES[match.group(2)], headers={"Cache-Control": "no-cache"})
