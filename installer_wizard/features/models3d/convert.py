import asyncio
import shutil
import tempfile
from pathlib import Path

from features.models3d import library

BLENDER_SCRIPT = """
import bpy, sys
src, dst = sys.argv[-2], sys.argv[-1]
if src.lower().endswith(".blend"):
    bpy.ops.wm.open_mainfile(filepath=src)
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.usd_import(filepath=src)
bpy.ops.export_scene.gltf(filepath=dst, export_format="GLB")
"""
NEEDS = {"blend": "blender", "usd": "blender", "usda": "blender", "usdc": "blender", "usdz": "blender", "dwg": "dwg2dxf"}


def tool(fmt: str) -> str | None:
    name = NEEDS.get(fmt)
    return shutil.which(name) if name else None


def needs_conversion(fmt: str) -> bool:
    return fmt in NEEDS


async def _run(*cmd: str, timeout: float = 300) -> int:
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    try:
        return await asyncio.wait_for(proc.wait(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return -1


async def convert(meta: dict, name: str) -> dict:
    fmt = library.ext_of(name)
    exe = tool(fmt)
    if not exe:
        program = "Blender" if NEEDS.get(fmt) == "blender" else "LibreDWG"
        meta["note"] = f"Per aprire i file .{fmt} serve {program} sul server: attiva «Conversione 3D» nelle impostazioni."
        return library.save_meta(meta)
    src = library.path(meta["id"], name)
    if fmt == "dwg":
        dst = src.with_suffix(".dxf")
        code = await _run(exe, "-y", "-o", str(dst), str(src))
    else:
        dst = src.with_suffix(".glb")
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as script:
            script.write(BLENDER_SCRIPT)
        code = await _run(exe, "-b", "--python", script.name, "--", str(src), str(dst), timeout=600)
        Path(script.name).unlink(missing_ok=True)
    if code != 0 or not dst.exists():
        meta["note"] = f"Conversione del file .{fmt} non riuscita."
        return library.save_meta(meta)
    meta = library.add_file(meta, dst.name, dst.read_bytes())
    meta["view"] = dst.name
    meta["note"] = ""
    return library.save_meta(meta)
