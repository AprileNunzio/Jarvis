import math

SHAPES = ("box", "cylinder", "cone", "sphere", "torus", "capsule", "wedge")


class Mesh:
    def __init__(self) -> None:
        self.pos: list[tuple] = []
        self.nrm: list[tuple] = []
        self.tri: list[tuple] = []

    def vertex(self, p, n) -> int:
        self.pos.append(p)
        self.nrm.append(n)
        return len(self.pos) - 1

    def quad(self, a, b, c, d, n) -> None:
        i = [self.vertex(p, n) for p in (a, b, c, d)]
        self.tri += [(i[0], i[1], i[2]), (i[0], i[2], i[3])]


def _norm(v):
    length = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / length for c in v)


def box(w, h, d) -> Mesh:
    m, x, y, z = Mesh(), w / 2, h / 2, d / 2
    m.quad((-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z), (0, 0, 1))
    m.quad((x, -y, -z), (-x, -y, -z), (-x, y, -z), (x, y, -z), (0, 0, -1))
    m.quad((x, -y, z), (x, -y, -z), (x, y, -z), (x, y, z), (1, 0, 0))
    m.quad((-x, -y, -z), (-x, -y, z), (-x, y, z), (-x, y, -z), (-1, 0, 0))
    m.quad((-x, y, z), (x, y, z), (x, y, -z), (-x, y, -z), (0, 1, 0))
    m.quad((-x, -y, -z), (x, -y, -z), (x, -y, z), (-x, -y, z), (0, -1, 0))
    return m


def wedge(w, h, d) -> Mesh:
    m, x, y, z = Mesh(), w / 2, h / 2, d / 2
    slope = _norm((0, d, h))
    m.quad((-x, -y, z), (x, -y, z), (x, y, -z), (-x, y, -z), slope)
    m.quad((x, -y, -z), (-x, -y, -z), (-x, y, -z), (x, y, -z), (0, 0, -1))
    m.quad((-x, -y, -z), (x, -y, -z), (x, -y, z), (-x, -y, z), (0, -1, 0))
    for sx in (-1, 1):
        a, b, c = (sx * x, -y, z), (sx * x, -y, -z), (sx * x, y, -z)
        i = [m.vertex(p, (sx, 0, 0)) for p in ((a, b, c) if sx > 0 else (b, a, c))]
        m.tri.append(tuple(i))
    return m


def lathe(profile, seg=32) -> Mesh:
    m = Mesh()
    rings = []
    for r, y, nr, ny in profile:
        ring = []
        for k in range(seg + 1):
            a = 2 * math.pi * k / seg
            c, s = math.cos(a), math.sin(a)
            ring.append(m.vertex((r * c, y, r * s), _norm((nr * c, ny, nr * s))))
        rings.append(ring)
    for j in range(len(rings) - 1):
        for k in range(seg):
            a, b, c, d = rings[j][k], rings[j][k + 1], rings[j + 1][k + 1], rings[j + 1][k]
            m.tri += [(a, c, b), (a, d, c)]
    return m


def _cap(m: Mesh, r, y, up, seg=32) -> None:
    if r <= 0:
        return
    n = (0, 1 if up else -1, 0)
    center = m.vertex((0, y, 0), n)
    ring = [m.vertex((r * math.cos(2 * math.pi * k / seg), y, r * math.sin(2 * math.pi * k / seg)), n) for k in range(seg + 1)]
    for k in range(seg):
        m.tri.append((center, ring[k + 1], ring[k]) if up else (center, ring[k], ring[k + 1]))


def cylinder(r_top, r_bottom, h, seg=32) -> Mesh:
    slope = (r_bottom - r_top) / h if h else 0
    m = lathe([(r_bottom, -h / 2, 1, slope), (r_top, h / 2, 1, slope)], seg)
    _cap(m, r_top, h / 2, True, seg)
    _cap(m, r_bottom, -h / 2, False, seg)
    return m


def sphere(r, rings=16, seg=32, y0=0.0, a0=-math.pi / 2, a1=math.pi / 2) -> list:
    prof = []
    for j in range(rings + 1):
        a = a0 + (a1 - a0) * j / rings
        prof.append((r * math.cos(a), y0 + r * math.sin(a), math.cos(a), math.sin(a)))
    return prof


def capsule(r, h, seg=32) -> Mesh:
    body = max(0.0, h - 2 * r) / 2
    prof = sphere(r, 8, seg, -body, -math.pi / 2, 0) + sphere(r, 8, seg, body, 0, math.pi / 2)
    return lathe(prof, seg)


def torus(r, tube, seg=40, sides=16) -> Mesh:
    m = Mesh()
    grid = []
    for i in range(seg + 1):
        u = 2 * math.pi * i / seg
        row = []
        for j in range(sides + 1):
            v = 2 * math.pi * j / sides
            cx, cz = math.cos(u), math.sin(u)
            p = ((r + tube * math.cos(v)) * cx, tube * math.sin(v), (r + tube * math.cos(v)) * cz)
            row.append(m.vertex(p, (math.cos(v) * cx, math.sin(v), math.cos(v) * cz)))
        grid.append(row)
    for i in range(seg):
        for j in range(sides):
            a, b, c, d = grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]
            m.tri += [(a, c, b), (a, d, c)]
    return m


def _num(v, default):
    try:
        return max(0.01, min(10000.0, float(v)))
    except (TypeError, ValueError):
        return default


def _vec(v, default):
    if isinstance(v, (int, float)):
        return (float(v),) * 3
    try:
        return tuple(float(x) for x in list(v)[:3]) if v and len(v) >= 3 else default
    except (TypeError, ValueError):
        return default


def primitive(part: dict) -> Mesh:
    shape = part.get("shape", "box")
    s = _vec(part.get("size"), (1.0, 1.0, 1.0))
    r = _num(part.get("radius"), max(s[0], s[2]) / 2)
    h = _num(part.get("height"), s[1])
    if shape == "cylinder":
        return cylinder(_num(part.get("radius_top"), r), _num(part.get("radius_bottom"), r), h)
    if shape == "cone":
        return cylinder(_num(part.get("radius_top"), 0.0001), _num(part.get("radius_bottom"), r), h)
    if shape == "sphere":
        return lathe(sphere(r), 32)
    if shape == "capsule":
        return capsule(r, h)
    if shape == "torus":
        return torus(r, _num(part.get("tube"), r * 0.25))
    if shape == "wedge":
        return wedge(*[max(0.01, c) for c in s])
    return box(*[max(0.01, c) for c in s])


def _rotation(rx, ry, rz):
    a, b, c = (math.radians(v) for v in (rx, ry, rz))
    ca, sa, cb, sb, cc, sc = math.cos(a), math.sin(a), math.cos(b), math.sin(b), math.cos(c), math.sin(c)
    return ((cb * cc, -cb * sc, sb),
            (ca * sc + sa * sb * cc, ca * cc - sa * sb * sc, -sa * cb),
            (sa * sc - ca * sb * cc, sa * cc + ca * sb * sc, ca * cb))


def placed(part: dict) -> Mesh:
    m = primitive(part)
    R = _rotation(*_vec(part.get("rotation"), (0.0, 0.0, 0.0)))
    t = _vec(part.get("position"), (0.0, 0.0, 0.0))
    k = _vec(part.get("scale"), (1.0, 1.0, 1.0))
    mul = lambda v: tuple(sum(R[i][j] * v[j] for j in range(3)) for i in range(3))
    m.pos = [tuple(a + b for a, b in zip(mul(tuple(p[i] * k[i] for i in range(3))), t)) for p in m.pos]
    m.nrm = [_norm(mul(tuple(n[i] / k[i] for i in range(3)))) for n in m.nrm]
    return m
