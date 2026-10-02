(function (J) {
  "use strict";
  const H = (J.Holo = J.Holo || {});
  const S = (x) => (x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x));
  const band = (v, a, b) => S((v - a) / (b - a));
  const bell = (dx, dy, rx, ry) => Math.exp(-(dx * dx) / (rx * rx) - (dy * dy) / (ry * ry));
  const NAMES = ["jawOpen", "mouthWide", "mouthPucker", "mouthClose", "mouthSmile", "mouthFrown",
                 "browUp", "browInner", "browDown", "eyeOpen", "eyeSquint", "eyeWide"];
  const JAW_ANGLE = 0.3;

  function field(L) {
    const F = L.F, m = L.mouth, e = L.eye, jaw = L.jaw, ca = Math.cos(JAW_ANGLE), sa = Math.sin(JAW_ANGLE);
    const cheekY = m.y + (e.y - m.y) * 0.55;
    return (x, y, z) => {
      const ax = Math.abs(x), sx = Math.sign(x);
      const lipFront = band(z, m.z - 0.9 * F, m.z - 0.3 * F), eyeFront = band(z, e.z - 0.7 * F, e.z - 0.2 * F);
      const lips = bell(x, y - m.y, m.w * 1.35, 0.5 * F) * lipFront;
      const seam = bell(x, y - m.y, m.w * 1.2, 0.3 * F) * lipFront;
      const corner = bell(ax - m.w, y - m.y, 0.45 * F, 0.4 * F) * lipFront;
      const cheek = bell(ax - 0.95 * e.x, y - cheekY, 0.45 * F, 0.4 * F) * lipFront;
      const brow = bell(ax - e.x, y - (e.y + 0.45 * F), 0.6 * F, 0.32 * F) * eyeFront;
      const inner = bell(ax - 0.45 * e.x, y - (e.y + 0.4 * F), 0.35 * F, 0.3 * F) * eyeFront;
      const lid = bell(ax - e.x, y - e.y, 0.48 * F, 0.32 * F) * eyeFront;
      const slit = bell(ax - e.x, y - e.y, 0.36 * F, 0.12 * F) * eyeFront;
      const jw = band(y, m.y + 0.06 * F, m.y - 0.12 * F) * band(y, L.chin.y - F, L.chin.y - 0.25 * F) * band(z, jaw.z, jaw.z + 0.8 * F);
      const qy = y - jaw.y, qz = z - jaw.z;
      const above = Math.max(0, y - (e.y - 0.12 * F)), below = Math.max(0, e.y - 0.1 * F - y);
      return {
        jawOpen: [0, (jaw.y + qy * ca - qz * sa - y) * jw, (jaw.z + qy * sa + qz * ca - z) * jw],
        mouthWide: [x * 0.25 * lips, 0, -0.05 * F * lips],
        mouthPucker: [-x * 0.4 * lips, 0, 0.16 * F * seam],
        mouthClose: [0, -(y - m.y) * 0.55 * seam, 0],
        mouthSmile: [sx * 0.07 * F * corner, 0.15 * F * corner + 0.06 * F * cheek, -0.03 * F * corner + 0.04 * F * cheek],
        mouthFrown: [-sx * 0.02 * F * corner, -0.14 * F * corner, 0],
        browUp: [0, 0.13 * F * brow, 0.01 * F * brow],
        browInner: [0, 0.12 * F * inner, 0],
        browDown: [-sx * 0.05 * F * brow, -0.09 * F * brow, 0.02 * F * brow],
        eyeOpen: [0, (y - e.y) * 0.55 * lid, -0.08 * F * slit],
        eyeSquint: [0, (-above * 0.35 + below * 0.5) * lid, 0],
        eyeWide: [0, Math.max(0, y - e.y) * 0.3 * lid, 0],
      };
    };
  }

  function build(base, L) {
    const f = field(L), n = base.length / 3, acc = {};
    NAMES.forEach((k) => (acc[k] = { idx: [], d: [] }));
    for (let i = 0; i < n; i++) {
      const out = f(base[i * 3], base[i * 3 + 1], base[i * 3 + 2]);
      for (const k of NAMES) {
        const d = out[k];
        if (Math.abs(d[0]) + Math.abs(d[1]) + Math.abs(d[2]) < 1e-6) continue;
        acc[k].idx.push(i); acc[k].d.push(d[0], d[1], d[2]);
      }
    }
    const shapes = {};
    for (const k of NAMES) shapes[k] = { idx: Int32Array.from(acc[k].idx), d: Float32Array.from(acc[k].d) };
    return shapes;
  }

  H.Shapes = { NAMES, build };
})(window.Jarvis3D);
