(function (J) {
  "use strict";
  const { THREE, REGIONS, damp, hash, rng, quad } = J;

  const NEURON_VERT = `
    uniform float uTime, uScale;
    attribute vec3 color; attribute float aSize, aBirth, aSel;
    varying vec3 vColor; varying float vFlash, vSel;
    void main() {
      float age = uTime - aBirth;
      vFlash = aBirth > 0.0 ? exp(-age * 1.2) : 0.0;
      float grow = aBirth > 0.0 ? smoothstep(0.0, 1.2, age) : 1.0;
      vColor = color; vSel = aSel;
      vec4 mv = modelViewMatrix * vec4(position, 1.0);
      float pulse = 1.0 + 0.18 * sin(uTime * 2.4 + position.x * 7.0 + position.z * 5.0);
      gl_PointSize = aSize * uScale * pulse * grow * (1.0 + vFlash * 2.5 + aSel * 0.9) * (4.0 / -mv.z);
      gl_Position = projectionMatrix * mv;
    }`;
  const NEURON_FRAG = `
    uniform float uOpacity;
    varying vec3 vColor; varying float vFlash, vSel;
    void main() {
      float d = length(gl_PointCoord - 0.5);
      if (d > 0.5) discard;
      float core = smoothstep(0.5, 0.0, d);
      float ring = vSel * smoothstep(0.06, 0.0, abs(d - 0.42));
      vec3 c = mix(vColor, vec3(1.0), core * 0.55 + vFlash * 0.6);
      gl_FragColor = vec4(c, (core * core + ring + vFlash * core) * uOpacity);
    }`;
  const SYN_VERT = `
    uniform float uTime;
    attribute vec3 color; attribute float aT, aOffset;
    varying vec3 vColor; varying float vPulse, vT;
    void main() {
      vColor = color; vT = aT;
      float head = fract(uTime * 0.35 + aOffset);
      vPulse = smoothstep(0.12, 0.0, abs(aT - head));
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }`;
  const SYN_FRAG = `
    uniform float uOpacity;
    varying vec3 vColor; varying float vPulse, vT;
    void main() { gl_FragColor = vec4(mix(vColor, vec3(1.0), vPulse * 0.6), (0.16 + vPulse * 0.85) * uOpacity); }`;

  function regionOf(p) {
    if (p.cb) return "LOCATION";
    const { x, y, z } = p;
    if (z > 0.38) return "CONCEPT";
    if (y > 0.12 && z > 0.02) return "SKILL";
    if (z < -0.62) return "DEVICE";
    if (y > 0.0) return "AGENT";
    if (Math.abs(x) > 0.42) return z > -0.05 ? "USER" : "MEMORY";
    return "MEMORY";
  }

  class HoloBrain {
    constructor(parent) {
      this.group = new THREE.Group();
      parent.add(this.group);
      this.opacity = 0;
      this.uniforms = { uTime: { value: 0 }, uOpacity: { value: 0 }, uScale: { value: 1 } };
      this.nodes = new Map();
      this.birth = new Map();
      this.selected = null;
      this.time = 0;
      this._buildAnatomy();
      this.neurons = null;
      this.synapses = null;
    }

    _surfacePoint(r) {
      if (r() < 0.14) {
        const u = r() * Math.PI * 2, v = Math.acos(2 * r() - 1);
        const p = { x: Math.sin(v) * Math.cos(u) * 0.6, y: -0.52 + Math.cos(v) * 0.27, z: -0.72 + Math.sin(v) * Math.sin(u) * 0.36, cb: true };
        p.y += 0.03 * Math.sin(p.x * 40);
        return p;
      }
      const u = r() * Math.PI * 2, v = Math.acos(2 * r() - 1);
      let dx = Math.sin(v) * Math.cos(u), dy = Math.cos(v), dz = Math.sin(v) * Math.sin(u);
      let a = 0.82, b = 0.72, c = 1.05;
      if (dy < -0.2) b *= 0.8;
      if (dz > 0.4 && dy < 0.1) b *= 0.9;
      let x = dx * a, y = dy * b, z = dz * c;
      if (y < 0 && Math.abs(x) > 0.4 && z > -0.5) { y -= 0.12 * (1 + dy); }
      const fissure = Math.exp(-Math.pow(x / 0.06, 2)) * Math.max(0, dy);
      const gyri = 1 + 0.035 * Math.sin(dx * 23 + dz * 9) * Math.sin(dy * 21 - dz * 13) - fissure * 0.1;
      return { x: x * gyri + Math.sign(x || 1) * 0.03, y: y * gyri + 0.08, z: z * gyri, cb: false };
    }

    _buildAnatomy() {
      const r = rng(42), N = 2600;
      const pos = new Float32Array(N * 3), col = new Float32Array(N * 3);
      this.anatomy = [];
      const color = new THREE.Color();
      for (let i = 0; i < N; i++) {
        const p = this._surfacePoint(r);
        p.region = regionOf(p);
        this.anatomy.push(p);
        pos.set([p.x, p.y, p.z], i * 3);
        color.set(REGIONS[p.region].color);
        col.set([color.r, color.g, color.b], i * 3);
      }
      const cell = 0.14, grid = new Map();
      const key = (x, y, z) => `${Math.floor(x / cell)},${Math.floor(y / cell)},${Math.floor(z / cell)}`;
      this.anatomy.forEach((p, i) => { const k = key(p.x, p.y, p.z); (grid.get(k) || grid.set(k, []).get(k)).push(i); });
      const lines = [], lineCol = [];
      this.anatomy.forEach((p, i) => {
        const cx = Math.floor(p.x / cell), cy = Math.floor(p.y / cell), cz = Math.floor(p.z / cell);
        const near = [];
        for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
          for (const j of grid.get(`${cx + a},${cy + b},${cz + c}`) || []) {
            if (j <= i) continue;
            const q = this.anatomy[j], d = (p.x - q.x) ** 2 + (p.y - q.y) ** 2 + (p.z - q.z) ** 2;
            if (d < cell * cell) near.push([d, j]);
          }
        }
        near.sort((m, n) => m[0] - n[0]).slice(0, 2).forEach(([, j]) => {
          const q = this.anatomy[j];
          lines.push(p.x, p.y, p.z, q.x, q.y, q.z);
          lineCol.push(col[i * 3], col[i * 3 + 1], col[i * 3 + 2], col[j * 3], col[j * 3 + 1], col[j * 3 + 2]);
        });
      });
      const dots = new THREE.BufferGeometry();
      dots.setAttribute("position", new THREE.BufferAttribute(pos, 3));
      dots.setAttribute("color", new THREE.BufferAttribute(col, 3));
      this.dotMat = new THREE.PointsMaterial({ size: 0.018, vertexColors: true, transparent: true, opacity: 0,
        blending: THREE.AdditiveBlending, depthWrite: false });
      this.group.add(new THREE.Points(dots, this.dotMat));
      const mesh = new THREE.BufferGeometry();
      mesh.setAttribute("position", new THREE.Float32BufferAttribute(lines, 3));
      mesh.setAttribute("color", new THREE.Float32BufferAttribute(lineCol, 3));
      this.meshMat = new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0,
        blending: THREE.AdditiveBlending, depthWrite: false });
      this.group.add(new THREE.LineSegments(mesh, this.meshMat));
      this.byRegion = {};
      this.anatomy.forEach((p) => (this.byRegion[p.region] = this.byRegion[p.region] || []).push(p));
    }

    _placeNeuron(node) {
      const region = REGIONS[node.node_type] ? node.node_type : "CONCEPT";
      const pool = this.byRegion[region] || this.anatomy;
      const r = rng(hash(node.id));
      const base = pool[Math.floor(r() * pool.length)];
      const depth = 0.72 + r() * 0.24;
      const cy = base.cb ? -0.52 : 0.08, cz = base.cb ? -0.72 : 0;
      return new THREE.Vector3(base.x * depth, cy + (base.y - cy) * depth, cz + (base.z - cz) * depth);
    }

    setGraph(graph, animateNew = true) {
      const nodes = graph.nodes || [], edges = graph.edges || [];
      const fresh = [];
      const seen = new Set();
      nodes.forEach((n) => {
        seen.add(n.id);
        if (!this.nodes.has(n.id)) {
          fresh.push(n);
          if (animateNew && this.ready) this.birth.set(n.id, this.time);
        }
        const prev = this.nodes.get(n.id);
        this.nodes.set(n.id, { node: n, pos: prev ? prev.pos : this._placeNeuron(n) });
      });
      for (const id of [...this.nodes.keys()]) if (!seen.has(id)) this.nodes.delete(id);
      this.edges = edges.filter((e) => this.nodes.has(e.source_id) && this.nodes.has(e.target_id));
      this._rebuild();
      this.ready = true;
      return fresh;
    }

    _rebuild() {
      const list = [...this.nodes.values()];
      this.index = list.map((x) => x.node.id);
      const n = list.length;
      const pos = new Float32Array(n * 3), col = new Float32Array(n * 3), size = new Float32Array(n),
        birth = new Float32Array(n), sel = new Float32Array(n);
      const degree = {};
      (this.edges || []).forEach((e) => { degree[e.source_id] = (degree[e.source_id] || 0) + 1; degree[e.target_id] = (degree[e.target_id] || 0) + 1; });
      const c = new THREE.Color();
      list.forEach((x, i) => {
        pos.set([x.pos.x, x.pos.y, x.pos.z], i * 3);
        c.set((REGIONS[x.node.node_type] || REGIONS.CONCEPT).color);
        col.set([c.r, c.g, c.b], i * 3);
        size[i] = 9 + Math.min(12, (degree[x.node.id] || 0) * 1.5);
        birth[i] = this.birth.get(x.node.id) || 0;
        sel[i] = this.selected === x.node.id ? 1 : 0;
      });
      if (this.neurons) { this.group.remove(this.neurons); this.neurons.geometry.dispose(); }
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
      g.setAttribute("color", new THREE.BufferAttribute(col, 3));
      g.setAttribute("aSize", new THREE.BufferAttribute(size, 1));
      g.setAttribute("aBirth", new THREE.BufferAttribute(birth, 1));
      g.setAttribute("aSel", new THREE.BufferAttribute(sel, 1));
      this.neurons = new THREE.Points(g, this.neuronMat || (this.neuronMat = new THREE.ShaderMaterial({
        uniforms: this.uniforms, vertexShader: NEURON_VERT, fragmentShader: NEURON_FRAG,
        transparent: true, depthWrite: false, blending: THREE.AdditiveBlending })));
      this.group.add(this.neurons);

      const SEG = 16, sp = [], sc = [], st = [], so = [];
      const a = new THREE.Vector3(), b = new THREE.Vector3(), m = new THREE.Vector3(), p0 = new THREE.Vector3(), p1 = new THREE.Vector3();
      const colA = new THREE.Color(), colB = new THREE.Color();
      (this.edges || []).forEach((e, k) => {
        a.copy(this.nodes.get(e.source_id).pos); b.copy(this.nodes.get(e.target_id).pos);
        m.addVectors(a, b).multiplyScalar(0.5).multiplyScalar(0.55);
        colA.set((REGIONS[this.nodes.get(e.source_id).node.node_type] || REGIONS.CONCEPT).color);
        colB.set((REGIONS[this.nodes.get(e.target_id).node.node_type] || REGIONS.CONCEPT).color);
        const off = (hash(e.source_id + e.target_id) % 1000) / 1000;
        for (let s = 0; s < SEG; s++) {
          const t0 = s / SEG, t1 = (s + 1) / SEG;
          quad(a, m, b, t0, p0); quad(a, m, b, t1, p1);
          sp.push(p0.x, p0.y, p0.z, p1.x, p1.y, p1.z);
          const c0 = colA.clone().lerp(colB, t0), c1 = colA.clone().lerp(colB, t1);
          sc.push(c0.r, c0.g, c0.b, c1.r, c1.g, c1.b);
          st.push(t0, t1); so.push(off, off);
        }
      });
      if (this.synapses) { this.group.remove(this.synapses); this.synapses.geometry.dispose(); }
      const sg = new THREE.BufferGeometry();
      sg.setAttribute("position", new THREE.Float32BufferAttribute(sp, 3));
      sg.setAttribute("color", new THREE.Float32BufferAttribute(sc, 3));
      sg.setAttribute("aT", new THREE.Float32BufferAttribute(st, 1));
      sg.setAttribute("aOffset", new THREE.Float32BufferAttribute(so, 1));
      this.synapses = new THREE.LineSegments(sg, this.synMat || (this.synMat = new THREE.ShaderMaterial({
        uniforms: this.uniforms, vertexShader: SYN_VERT, fragmentShader: SYN_FRAG,
        transparent: true, depthWrite: false, blending: THREE.AdditiveBlending })));
      this.group.add(this.synapses);
    }

    select(id) { this.selected = id; if (this.ready) this._rebuild(); }
    nodeAt(index) { return this.nodes.get(this.index[index]); }
    neighbours(id) {
      return (this.edges || []).filter((e) => e.source_id === id || e.target_id === id)
        .map((e) => ({ edge: e, other: this.nodes.get(e.source_id === id ? e.target_id : e.source_id).node }));
    }
    counts() {
      const out = {};
      for (const { node } of this.nodes.values()) out[node.node_type] = (out[node.node_type] || 0) + 1;
      return out;
    }
    update(t, dt) {
      this.time = t;
      this.uniforms.uTime.value = t;
      const o = this.uniforms.uOpacity.value = damp(this.uniforms.uOpacity.value, this.opacity, 2.5, dt);
      this.dotMat.opacity = o * 0.55;
      this.meshMat.opacity = o * 0.2;
      this.group.visible = o > 0.01;
      if (this.autoRotate) this.group.rotation.y = damp(this.group.rotation.y, Math.PI / 2 + Math.sin(t * 0.12) * 0.55, 1.5, dt);
    }
  }

  Object.assign(J, { HoloBrain });
})(window.Jarvis3D);
