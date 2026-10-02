(() => {
  const VER = window.JARVIS_ASSET_V ? `?v=${window.JARVIS_ASSET_V}` : "";
  const FFLATE = ["fflate.min.js"];
  const NEEDS = {
    glb: ["GLTFLoader.js"], gltf: ["GLTFLoader.js"], obj: ["MTLLoader.js", "OBJLoader.js"], stl: ["STLLoader.js"],
    ply: ["PLYLoader.js"], fbx: [...FFLATE, "NURBSUtils.js", "NURBSCurve.js", "FBXLoader.js"], dae: ["ColladaLoader.js"],
    "3mf": [...FFLATE, "3MFLoader.js"], amf: [...FFLATE, "AMFLoader.js"], "3ds": ["TDSLoader.js"],
    wrl: ["chevrotain.min.js", "VRMLLoader.js"], step: ["occt-import-js.js"], stp: ["occt-import-js.js"],
    iges: ["occt-import-js.js"], igs: ["occt-import-js.js"], brep: ["occt-import-js.js"], dxf: [],
  };
  const Z_UP = new Set(["stl", "3mf", "amf", "step", "stp", "iges", "igs", "brep", "3ds"]);
  const LABEL = { glb: "glTF", gltf: "glTF", obj: "OBJ", stl: "STL", ply: "PLY", fbx: "FBX", dae: "Collada", "3mf": "3MF",
    amf: "AMF", "3ds": "3DS", wrl: "VRML", step: "STEP", stp: "STEP", iges: "IGES", igs: "IGES", brep: "BREP", dxf: "DXF" };
  const scripts = {};

  const script = (name) => scripts[name] || (scripts[name] = new Promise((ok, ko) => {
    const s = document.createElement("script");
    s.src = `/vendor/${name}${VER}`; s.onload = ok; s.onerror = () => ko(new Error(`${name} non disponibile`));
    document.head.appendChild(s);
  }));

  async function ensure(fmt) {
    for (let i = 0; i < 30 && !window.THREE && document.querySelector('script[src*="three.min.js"]'); i++) {
      await new Promise((r) => setTimeout(r, 100));
    }
    if (!window.THREE) await script("three.min.js");
    if (!THREE.OrbitControls) await script("OrbitControls.js");
    for (const n of NEEDS[fmt] || []) {
      if (n === "GLTFLoader.js" && THREE.GLTFLoader) continue;
      await script(n);
    }
  }

  const steel = () => new THREE.MeshStandardMaterial({ color: 0xa7b4c4, metalness: 0.35, roughness: 0.45 });

  function fromGeometry(g) {
    if (!g.index && !g.attributes.normal && g.attributes.position.count % 3 !== 0) {
      return new THREE.Points(g, new THREE.PointsMaterial({ size: 0.01, sizeAttenuation: true, vertexColors: !!g.attributes.color }));
    }
    if (!g.attributes.normal) g.computeVertexNormals();
    const mat = steel();
    if (g.attributes.color) { mat.vertexColors = true; mat.color.set(0xffffff); }
    return new THREE.Mesh(g, mat);
  }

  function parseDXF(text) {
    const lines = text.split(/\r?\n/), pairs = [];
    for (let i = 0; i + 1 < lines.length; i += 2) pairs.push([+lines[i].trim(), lines[i + 1].trim()]);
    const seg = [], tri = [], ents = [];
    let cur = null;
    for (const [code, val] of pairs) {
      if (code === 0) { if (cur) ents.push(cur); cur = { type: val, v: {}, pts: [] }; continue; }
      if (!cur) continue;
      if (code === 10) cur.pts.push([+val, 0, 0]);
      else if (code === 20 && cur.pts.length) cur.pts[cur.pts.length - 1][1] = +val;
      else if (code === 30 && cur.pts.length) cur.pts[cur.pts.length - 1][2] = +val;
      else if ([11, 12, 13].includes(code)) cur.pts.push([+val, 0, 0]);
      else if ([21, 22, 23].includes(code) && cur.pts.length) cur.pts[cur.pts.length - 1][1] = +val;
      else if ([31, 32, 33].includes(code) && cur.pts.length) cur.pts[cur.pts.length - 1][2] = +val;
      else cur.v[code] = val;
    }
    if (cur) ents.push(cur);
    const line = (a, b) => seg.push(...a, ...b);
    const arc = (c, r, a0, a1) => {
      let span = a1 - a0; if (span <= 0) span += 360;
      const n = Math.max(8, Math.ceil(span / 6));
      for (let i = 0; i < n; i++) {
        const t0 = ((a0 + (span * i) / n) * Math.PI) / 180, t1 = ((a0 + (span * (i + 1)) / n) * Math.PI) / 180;
        line([c[0] + r * Math.cos(t0), c[1] + r * Math.sin(t0), c[2]], [c[0] + r * Math.cos(t1), c[1] + r * Math.sin(t1), c[2]]);
      }
    };
    let poly = null;
    for (const e of ents) {
      const p = e.pts;
      if (e.type === "LINE" && p.length >= 2) line(p[0], p[1]);
      else if (e.type === "LWPOLYLINE" && p.length > 1) {
        for (let i = 0; i + 1 < p.length; i++) line(p[i], p[i + 1]);
        if ((+e.v[70] || 0) & 1) line(p[p.length - 1], p[0]);
      } else if (e.type === "POLYLINE") poly = { pts: [], closed: (+e.v[70] || 0) & 1 };
      else if (e.type === "VERTEX" && poly && p.length) poly.pts.push(p[0]);
      else if (e.type === "SEQEND" && poly) {
        for (let i = 0; i + 1 < poly.pts.length; i++) line(poly.pts[i], poly.pts[i + 1]);
        if (poly.closed && poly.pts.length > 2) line(poly.pts[poly.pts.length - 1], poly.pts[0]);
        poly = null;
      } else if (e.type === "CIRCLE" && p.length) arc(p[0], +e.v[40] || 1, 0, 360);
      else if (e.type === "ARC" && p.length) arc(p[0], +e.v[40] || 1, +e.v[50] || 0, +e.v[51] || 360);
      else if (e.type === "3DFACE" && p.length >= 3) {
        tri.push(...p[0], ...p[1], ...p[2]);
        if (p.length > 3) tri.push(...p[0], ...p[2], ...p[3]);
      }
    }
    const group = new THREE.Group();
    if (seg.length) {
      const g = new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(seg, 3));
      group.add(new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: 0x29e0ff })));
    }
    if (tri.length) {
      const g = new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(tri, 3));
      g.computeVertexNormals();
      group.add(new THREE.Mesh(g, Object.assign(steel(), { side: THREE.DoubleSide })));
    }
    if (!group.children.length) throw new Error("Nessuna entità DXF riconosciuta");
    return group;
  }

  let occt = null;
  async function loadCad(fmt, url) {
    occt = occt || await window.occtimportjs({ locateFile: (f) => `/vendor/${f}${VER}` });
    const buf = new Uint8Array(await (await fetch(url)).arrayBuffer());
    const read = { step: "ReadStepFile", stp: "ReadStepFile", iges: "ReadIgesFile", igs: "ReadIgesFile", brep: "ReadBrepFile" }[fmt];
    const res = occt[read](buf, null);
    if (!res.success) throw new Error("File CAD non leggibile");
    const group = new THREE.Group();
    for (const m of res.meshes) {
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.Float32BufferAttribute(m.attributes.position.array, 3));
      if (m.attributes.normal) g.setAttribute("normal", new THREE.Float32BufferAttribute(m.attributes.normal.array, 3));
      if (m.index) g.setIndex(m.index.array);
      if (!m.attributes.normal) g.computeVertexNormals();
      const mat = steel();
      if (m.color) mat.color.setRGB(m.color[0], m.color[1], m.color[2]);
      group.add(new THREE.Mesh(g, mat));
    }
    return group;
  }

  async function loadModel(d) {
    const fmt = d.format, base = d.url, url = base + encodeURIComponent(d.main);
    await ensure(fmt);
    const files = (d.files || []).map((f) => f.name);
    if (fmt === "glb" || fmt === "gltf") { const g = await new THREE.GLTFLoader().loadAsync(url); return { obj: g.scene, clips: g.animations }; }
    if (fmt === "obj") {
      const loader = new THREE.OBJLoader(), mtl = files.find((n) => n.toLowerCase().endsWith(".mtl"));
      if (mtl) {
        const mats = await new THREE.MTLLoader().setPath(base).loadAsync(encodeURIComponent(mtl));
        mats.preload(); loader.setMaterials(mats);
      }
      return { obj: await loader.loadAsync(url) };
    }
    if (fmt === "stl") return { obj: fromGeometry(await new THREE.STLLoader().loadAsync(url)) };
    if (fmt === "ply") return { obj: fromGeometry(await new THREE.PLYLoader().loadAsync(url)) };
    if (fmt === "fbx") { const o = await new THREE.FBXLoader().loadAsync(url); return { obj: o, clips: o.animations }; }
    if (fmt === "dae") { const c = await new THREE.ColladaLoader().loadAsync(url); return { obj: c.scene, clips: c.animations || [] }; }
    if (fmt === "3mf") return { obj: await new THREE.ThreeMFLoader().loadAsync(url) };
    if (fmt === "amf") return { obj: await new THREE.AMFLoader().loadAsync(url) };
    if (fmt === "3ds") return { obj: await new THREE.TDSLoader().setResourcePath(base).loadAsync(url) };
    if (fmt === "wrl") return { obj: await new THREE.VRMLLoader().loadAsync(url) };
    if (fmt === "dxf") return { obj: parseDXF(await (await fetch(url)).text()) };
    if (NEEDS[fmt]) return { obj: await loadCad(fmt, url) };
    throw new Error(`Formato .${fmt} non visualizzabile`);
  }

  function stats(obj) {
    let tris = 0;
    obj.traverse((o) => {
      if (!o.isMesh) return;
      const g = o.geometry;
      tris += g.index ? g.index.count / 3 : g.attributes.position.count / 3;
    });
    return Math.round(tris);
  }

  const fmtSize = (v) => (v >= 100 ? `${(v / 100).toFixed(2)} m` : v >= 1 ? `${v.toFixed(1)} cm` : `${(v * 10).toFixed(1)} mm`);

  function mount(el, d, ctx) {
    const files = d.files || [];
    el.innerHTML = `<div class="v3-head"><span class="v3-title">🧊 ${ctx.esc(d.title || "Modello 3D")}</span>
        <span class="v3-tag">${ctx.esc(LABEL[d.format] || (d.format || "").toUpperCase())}</span></div>
      <div class="v3-stage"><canvas></canvas><div class="v3-msg">Caricamento del modello…</div>
        <div class="v3-tools"><button data-a="spin" title="Rotazione automatica">⟳</button><button data-a="wire" title="Reticolo">▦</button>
          <button data-a="fit" title="Inquadra">⤢</button></div></div>
      <div class="v3-info"><span class="v3-stats"></span>${d.note ? `<span class="v3-note">${ctx.esc(d.note)}</span>` : ""}</div>
      <div class="v3-files">${files.map((f) => `<a href="${d.url}${encodeURIComponent(f.name)}" download>${ctx.esc(f.name)}</a>`).join("")}</div>`;
    const st = { el, id: d.id, alive: true, spin: true, wire: false };
    el._v3 = st;
    start(st, d).catch((err) => { const m = el.querySelector(".v3-msg"); if (m) { m.textContent = `⚠ ${err.message}`; m.classList.add("err"); } });
  }

  async function start(st, d) {
    if (!d.main || !NEEDS[d.format]) throw new Error(d.note || `Formato .${d.format} non visualizzabile`);
    const { obj, clips } = await loadModel(d);
    if (!st.alive) return;
    const stage = st.el.querySelector(".v3-stage"), canvas = stage.querySelector("canvas");
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    if (THREE.sRGBEncoding) renderer.outputEncoding = THREE.sRGBEncoding;
    const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(40, 1, 0.01, 1000);
    scene.add(new THREE.HemisphereLight(0xdff6ff, 0x0b1a2a, 1.0));
    const sun = new THREE.DirectionalLight(0xffffff, 0.9); sun.position.set(3, 5, 4); scene.add(sun);
    const rim = new THREE.DirectionalLight(0x29e0ff, 0.5); rim.position.set(-4, 2, -3); scene.add(rim);
    const pivot = new THREE.Group(); scene.add(pivot);
    if (Z_UP.has(d.format)) obj.rotation.x = -Math.PI / 2;
    pivot.add(obj);
    obj.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(obj), size = new THREE.Vector3(), center = new THREE.Vector3();
    box.getSize(size); box.getCenter(center);
    const k = 2 / Math.max(size.x, size.y, size.z, 1e-6);
    obj.position.sub(center.clone()).multiplyScalar(1);
    pivot.scale.setScalar(k);
    pivot.position.y = 0;
    const grid = new THREE.GridHelper(4, 20, 0x29e0ff, 0x123044);
    grid.position.y = -(size.y * k) / 2; grid.material.transparent = true; grid.material.opacity = 0.35; scene.add(grid);
    const controls = new THREE.OrbitControls(camera, canvas);
    controls.enableDamping = true; controls.autoRotate = true; controls.autoRotateSpeed = 1.6;
    controls.addEventListener("start", () => { controls.autoRotate = false; st.spin = false; });
    const fit = () => { camera.position.set(2.2, 1.6, 2.6); controls.target.set(0, 0, 0); controls.update(); };
    fit();
    const mixer = clips && clips.length ? new THREE.AnimationMixer(obj) : null;
    if (mixer) mixer.clipAction(clips[0]).play();
    const unit = ["glb", "gltf"].includes(d.format) ? 100 : ["stl", "3mf", "amf", "step", "stp", "iges", "igs", "brep"].includes(d.format) ? 0.1 : 1;
    st.el.querySelector(".v3-stats").textContent = `${stats(obj).toLocaleString("it-IT")} triangoli · ${[size.x, size.y, size.z]
      .map((v) => fmtSize(v * unit)).join(" × ")}${clips && clips.length ? ` · ${clips.length} animazioni` : ""}`;
    st.el.querySelector(".v3-msg").remove();
    st.el.querySelector(".v3-tools").addEventListener("click", (e) => {
      const a = e.target.dataset.a;
      if (a === "spin") controls.autoRotate = st.spin = !st.spin;
      if (a === "fit") fit();
      if (a === "wire") {
        st.wire = !st.wire;
        obj.traverse((o) => { if (o.material) [].concat(o.material).forEach((m) => { m.wireframe = st.wire; }); });
      }
    });
    const clock = new THREE.Clock();
    const frame = () => {
      if (!st.alive || !st.el.isConnected) { renderer.dispose(); return; }
      const w = stage.clientWidth, h = stage.clientHeight;
      if (canvas.width !== Math.floor(w * renderer.getPixelRatio()) || canvas.height !== Math.floor(h * renderer.getPixelRatio())) {
        renderer.setSize(w, h, false); camera.aspect = w / Math.max(1, h); camera.updateProjectionMatrix();
      }
      const dt = clock.getDelta();
      if (mixer) mixer.update(dt);
      controls.update();
      renderer.render(scene, camera);
      st.raf = requestAnimationFrame(frame);
    };
    st.renderer = renderer;
    frame();
  }

  JarvisDesk.register("viewer_3d", {
    render(el, d, ctx) { if (el._v3) el._v3.alive = false; mount(el, d, ctx); },
    update(el, d, ctx) { if (el._v3 && el._v3.id === d.id) return; if (el._v3) el._v3.alive = false; mount(el, d, ctx); },
    destroy(el) { if (el._v3) { el._v3.alive = false; cancelAnimationFrame(el._v3.raf); if (el._v3.renderer) el._v3.renderer.dispose(); } },
  });
})();
