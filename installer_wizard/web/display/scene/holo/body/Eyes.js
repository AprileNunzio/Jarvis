(function (J) {
  "use strict";
  const { THREE } = J;
  const H = (J.Holo = J.Holo || {});
  const N = 24;

  function circle(r, n) {
    const v = [];
    for (let i = 0; i <= n; i++) { const a = (i / n) * Math.PI * 2; v.push(Math.cos(a) * r, Math.sin(a) * r, 0); }
    return new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(v, 3));
  }

  function arc() {
    return new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(new Float32Array((N + 1) * 3), 3));
  }

  class Eyes {
    constructor(avatar) {
      this.a = avatar;
      const L = avatar.L, F = L.F, C = avatar.uniforms.uColor.value;
      const line = (op) => new THREE.LineBasicMaterial({ color: C.clone(), transparent: true, opacity: op,
        blending: THREE.AdditiveBlending, depthWrite: false });
      this.W = F * 0.42; this.Hh = F * 0.2;
      this.mats = [];
      this.eyes = [-1, 1].map((sx) => {
        const g = new THREE.Group();
        g.position.set(sx * L.eye.x, L.eye.y, L.eye.z + F * 0.05);
        const upper = new THREE.Line(arc(), line(0.7)), lower = new THREE.Line(arc(), line(0.45));
        const iris = new THREE.LineLoop(circle(F * 0.15, 28), line(0.9));
        const pupil = new THREE.Mesh(new THREE.CircleGeometry(F * 0.06, 18),
          new THREE.MeshBasicMaterial({ color: C.clone(), transparent: true, opacity: 0.9, depthWrite: false }));
        iris.add(pupil);
        g.add(upper, lower, iris);
        Object.assign(g, { upper, lower, iris, sx });
        this.mats.push([upper.material, 0.7], [lower.material, 0.45], [iris.material, 0.9], [pupil.material, 0.9]);
        avatar.headBone.add(g);
        return g;
      });
    }

    _lid(lineObj, h, sx) {
      const p = lineObj.geometry.attributes.position, W = this.W;
      for (let i = 0; i <= N; i++) {
        const u = i / N, x = (u - 0.5) * 2 * W, k = 1 - (x / W) * (x / W);
        p.setXYZ(i, x, h * k * (1 + 0.25 * sx * x / W), 0);
      }
      p.needsUpdate = true;
    }

    update(t, dt, pose) {
      const F = this.a.L.F, m = pose.morph, op = this.a.uniforms.uOpacity.value;
      const open = Math.max(0, Math.min(1.3, m.eyeOpen == null ? 1 : m.eyeOpen));
      const brow = (m.browUp || 0) * 0.15 - (m.browDown || 0) * 0.15;
      this.eyes.forEach((g) => {
        this._lid(g.upper, this.Hh * (open + brow) + F * 0.01, g.sx);
        this._lid(g.lower, -this.Hh * 0.55 * Math.min(1, open) - F * 0.01, g.sx);
        g.iris.position.set(pose.lookX * F * 0.22, pose.lookY * F * 0.12, 0);
        g.iris.scale.set(1, Math.max(0.02, Math.min(1, open * 1.1)), 1);
        g.iris.visible = open > 0.08;
      });
      const c = this.a.uniforms.uColor.value;
      this.mats.forEach(([mat, base]) => { mat.color.copy(c); mat.opacity = base * op; });
    }
  }

  H.Eyes = Eyes;
})(window.Jarvis3D);
