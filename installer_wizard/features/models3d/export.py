import json
import struct

from features.models3d.mesh import Mesh, placed

CM_TO_M, CM_TO_MM = 0.01, 10.0


def _rgb(color) -> tuple:
    text = str(color or "#9aa4b2").lstrip("#")
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    try:
        return tuple(int(text[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return (0.6, 0.64, 0.7)


def build(parts: list[dict]) -> list[tuple[dict, Mesh]]:
    return [(p, placed(p)) for p in parts]


def _pad(data: bytes, fill: bytes = b"\x00") -> bytes:
    return data + fill * ((4 - len(data) % 4) % 4)


def glb(meshes: list[tuple[dict, Mesh]], name: str) -> bytes:
    gltf = {"asset": {"version": "2.0", "generator": "Jarvis"}, "scene": 0,
            "scenes": [{"name": name, "nodes": [0]}],
            "nodes": [{"name": name, "children": list(range(1, len(meshes) + 1))}],
            "meshes": [], "materials": [], "accessors": [], "bufferViews": [], "buffers": []}
    blob = bytearray()

    def view(data: bytes, target: int) -> int:
        gltf["bufferViews"].append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(data), "target": target})
        blob.extend(_pad(data))
        return len(gltf["bufferViews"]) - 1

    for i, (part, m) in enumerate(meshes):
        pos = [c * CM_TO_M for p in m.pos for c in p]
        nrm = [c for n in m.nrm for c in n]
        idx = [i for t in m.tri for i in t]
        xs, ys, zs = pos[0::3], pos[1::3], pos[2::3]
        acc = len(gltf["accessors"])
        gltf["accessors"] += [
            {"bufferView": view(struct.pack(f"<{len(pos)}f", *pos), 34962), "componentType": 5126, "count": len(m.pos),
             "type": "VEC3", "min": [min(xs), min(ys), min(zs)], "max": [max(xs), max(ys), max(zs)]},
            {"bufferView": view(struct.pack(f"<{len(nrm)}f", *nrm), 34962), "componentType": 5126, "count": len(m.nrm), "type": "VEC3"},
            {"bufferView": view(struct.pack(f"<{len(idx)}I", *idx), 34963), "componentType": 5125, "count": len(idx), "type": "SCALAR"},
        ]
        metal = 1.0 if part.get("metal") else 0.0
        gltf["materials"].append({"name": part.get("material") or part.get("name") or f"parte {i + 1}",
                                  "pbrMetallicRoughness": {"baseColorFactor": [*_rgb(part.get("color")), 1.0],
                                                           "metallicFactor": metal, "roughnessFactor": 0.35 if metal else 0.7}})
        gltf["meshes"].append({"name": part.get("name") or f"parte {i + 1}",
                               "primitives": [{"attributes": {"POSITION": acc, "NORMAL": acc + 1}, "indices": acc + 2, "material": i}]})
        gltf["nodes"].append({"name": part.get("name") or f"parte {i + 1}", "mesh": i})
    gltf["buffers"].append({"byteLength": len(blob)})
    head = _pad(json.dumps(gltf, separators=(",", ":")).encode(), b" ")
    body = bytes(blob)
    total = 12 + 8 + len(head) + 8 + len(body)
    return (struct.pack("<4sII", b"glTF", 2, total) + struct.pack("<I4s", len(head), b"JSON") + head
            + struct.pack("<I4s", len(body), b"BIN\x00") + body)


def stl(meshes: list[tuple[dict, Mesh]], name: str) -> bytes:
    tris = []
    for _, m in meshes:
        for a, b, c in m.tri:
            pa, pb, pc = ((x * CM_TO_MM, -z * CM_TO_MM, y * CM_TO_MM) for x, y, z in (m.pos[i] for i in (a, b, c)))
            u = [pb[k] - pa[k] for k in range(3)]
            v = [pc[k] - pa[k] for k in range(3)]
            n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            length = sum(x * x for x in n) ** 0.5 or 1.0
            tris.append(struct.pack("<12fH", *(x / length for x in n), *pa, *pb, *pc, 0))
    header = f"Jarvis {name} (mm, Z in alto)".encode()[:80].ljust(80, b" ")
    return header + struct.pack("<I", len(tris)) + b"".join(tris)


def obj(meshes: list[tuple[dict, Mesh]], name: str, mtl_name: str) -> tuple[bytes, bytes]:
    lines, mats, base = [f"# Jarvis — {name} (cm)", f"mtllib {mtl_name}"], [], 1
    for i, (part, m) in enumerate(meshes):
        mat = f"m{i}"
        r, g, b = _rgb(part.get("color"))
        mats += [f"newmtl {mat}", f"Kd {r:.4f} {g:.4f} {b:.4f}", f"Ks {0.6 if part.get('metal') else 0.1:.2f} 0.1 0.1", "Ns 60", ""]
        lines.append(f"o {(part.get('name') or f'parte_{i + 1}').replace(' ', '_')}")
        lines.append(f"usemtl {mat}")
        lines += [f"v {x:.4f} {y:.4f} {z:.4f}" for x, y, z in m.pos]
        lines += [f"vn {x:.4f} {y:.4f} {z:.4f}" for x, y, z in m.nrm]
        lines += [f"f {a + base}//{a + base} {b + base}//{b + base} {c + base}//{c + base}" for a, b, c in m.tri]
        base += len(m.pos)
    return "\n".join(lines).encode(), "\n".join(mats).encode()
