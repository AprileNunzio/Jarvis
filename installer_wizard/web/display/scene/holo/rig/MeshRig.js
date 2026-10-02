(function (J) {
  "use strict";
  const { THREE } = J;
  const H = (J.Holo = J.Holo || {});
  const LEVELS = 48;
  const S = (x) => (x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x));

  class MeshRig {
    constructor(geometry, L) {
      this.L = L;
      this.pos = geometry.attributes.position;
      this.nrm = geometry.attributes.normal;
      this.base = Float32Array.from(this.pos.array);
      this.baseN = Float32Array.from(this.nrm.array);
      this.work = new Float32Array(this.base.length);
      this.shapes = H.Shapes.build(this.base, L);
      const n = this.pos.count, a = L.shoulderY + L.F * 0.2, b = L.chin.y - L.F * 0.3;
      this.level = new Uint8Array(n);
      for (let i = 0; i < n; i++) this.level[i] = Math.round(S((this.base[i * 3 + 1] - a) / Math.max(1e-4, b - a)) * (LEVELS - 1));
      this.mats = Array.from({ length: LEVELS }, () => new THREE.Matrix4());
      this.rots = Array.from({ length: LEVELS }, () => new THREE.Matrix3());
      this.headMatrix = this.mats[LEVELS - 1];
      this._e = new THREE.Euler();
      this._v = new THREE.Vector3();
    }

    _bone(k, pose, out) {
      const p = this.L.neck;
      this._e.set(pose.rx * k, pose.ry * k, pose.rz * k);
      out.makeRotationFromEuler(this._e);
      this._v.copy(p).applyMatrix4(out);
      out.setPosition(p.x - this._v.x + pose.px * k, p.y - this._v.y + pose.py * k, p.z - this._v.z);
    }

    _morph(morph) {
      const W = this.work;
      W.set(this.base);
      for (const name in this.shapes) {
        const w = morph[name] || 0;
        if (Math.abs(w) < 1e-3) continue;
        const { idx, d } = this.shapes[name];
        for (let j = 0; j < idx.length; j++) {
          const o = idx[j] * 3, q = j * 3;
          W[o] += d[q] * w; W[o + 1] += d[q + 1] * w; W[o + 2] += d[q + 2] * w;
        }
      }
    }

    apply(pose) {
      this._morph(pose.morph);
      for (let k = 0; k < LEVELS; k++) {
        this._bone(k / (LEVELS - 1), pose, this.mats[k]);
        this.rots[k].setFromMatrix4(this.mats[k]);
      }
      const W = this.work, P = this.pos.array, N = this.nrm.array, B = this.baseN, lv = this.level;
      for (let i = 0, n = this.pos.count; i < n; i++) {
        const e = this.mats[lv[i]].elements, r = this.rots[lv[i]].elements, o = i * 3;
        const x = W[o], y = W[o + 1], z = W[o + 2], a = B[o], b = B[o + 1], c = B[o + 2];
        P[o] = e[0] * x + e[4] * y + e[8] * z + e[12];
        P[o + 1] = e[1] * x + e[5] * y + e[9] * z + e[13];
        P[o + 2] = e[2] * x + e[6] * y + e[10] * z + e[14];
        N[o] = r[0] * a + r[3] * b + r[6] * c;
        N[o + 1] = r[1] * a + r[4] * b + r[7] * c;
        N[o + 2] = r[2] * a + r[5] * b + r[8] * c;
      }
      this.pos.needsUpdate = true;
      this.nrm.needsUpdate = true;
    }

    playClip() { return false; }
  }

  H.MeshRig = MeshRig;
})(window.Jarvis3D);
