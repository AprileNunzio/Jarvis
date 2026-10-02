(function (global) {
  "use strict";
  const MODES = ["auto", "full", "light"];
  const KEY_PREF = "jarvis.avatar";
  const KEY_FPS = "jarvis.avatar.fps";
  const store = {
    get(k) { try { return global.localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { v === null ? global.localStorage.removeItem(k) : global.localStorage.setItem(k, v); } catch (e) {} },
  };

  const SOFTWARE = /swiftshader|llvmpipe|softpipe|basic render|software|lavapipe/i;
  const DEDICATED = /nvidia|geforce|quadro|tesla|rtx|gtx|radeon\s*(rx|pro|r9|r7|vii|hd\s*[5-9]\d{3})|intel.*\barc\b|apple m\d/i;
  const INTEGRATED = /intel|uhd|iris|hd graphics|radeon\(tm\) graphics|radeon graphics|vega|mali|adreno|powervr|videocore|apple gpu/i;

  function probe() {
    const nav = global.navigator || {};
    const info = { webgl: false, software: false, dedicated: false, integrated: false, renderer: "",
                   cores: nav.hardwareConcurrency || 0, memory: nav.deviceMemory || 0,
                   mobile: /Android|iPhone|iPad|Mobile/i.test(nav.userAgent || "") };
    try {
      const canvas = document.createElement("canvas");
      let gl = canvas.getContext("webgl", { failIfMajorPerformanceCaveat: true });
      if (!gl) {
        gl = document.createElement("canvas").getContext("webgl");
        info.software = !!gl;
      }
      if (gl) {
        info.webgl = true;
        const dbg = gl.getExtension("WEBGL_debug_renderer_info");
        info.renderer = String(gl.getParameter(dbg ? dbg.UNMASKED_RENDERER_WEBGL : gl.RENDERER) || "");
        const lose = gl.getExtension("WEBGL_lose_context");
        if (lose) lose.loseContext();
      }
    } catch (e) { }
    if (SOFTWARE.test(info.renderer)) info.software = true;
    info.dedicated = !info.software && DEDICATED.test(info.renderer);
    info.integrated = !info.software && !info.dedicated && INTEGRATED.test(info.renderer);
    return info;
  }

  function gpuName(renderer) {
    const m = renderer.match(/ANGLE \([^,]*,\s*([^,]+?)(?:\s+Direct3D|\s+\(0x|\s*,|\))/);
    return (m ? m[1] : renderer).replace(/\((R|TM)\)/g, "").replace(/\s+/g, " ").trim().slice(0, 60);
  }

  function decideAuto(info) {
    if (!info.webgl) return ["light", "WebGL non disponibile"];
    if (info.software) return ["light", "grafica senza accelerazione hardware"];
    const cached = JSON.parse(store.get(KEY_FPS) || "null");
    if (cached && cached.renderer === info.renderer) return ["light", `3D poco fluido su questo dispositivo (${cached.fps} fps)`];
    if (info.mobile) return ["light", "dispositivo mobile: risparmio di batteria"];
    if (info.dedicated) {
      if ((info.cores && info.cores < 4) || (info.memory && info.memory < 4)) return ["light", "GPU dedicata ma processore o memoria limitati"];
      return ["full", `GPU dedicata: ${gpuName(info.renderer)}`];
    }
    if (info.integrated) return ["light", `GPU integrata: ${gpuName(info.renderer)}`];
    return info.cores >= 8 && (!info.memory || info.memory >= 8)
      ? ["full", `hardware potente (${info.cores} core)`] : ["light", "hardware nella media"];
  }

  function choose(systemPref) {
    const local = store.get(KEY_PREF);
    const devicePref = MODES.includes(local) ? local : "";
    const pref = devicePref || (MODES.includes(systemPref) ? systemPref : "auto");
    const info = probe();
    let mode, reason;
    if (pref === "light") [mode, reason] = ["light", "scelta nelle impostazioni"];
    else if (pref === "full") [mode, reason] = info.webgl ? ["full", "scelta nelle impostazioni"] : ["light", "WebGL non disponibile"];
    else [mode, reason] = decideAuto(info);
    return { mode, reason, pref, devicePref, auto: pref === "auto", info };
  }

  function setDevicePref(value) {
    store.set(KEY_PREF, MODES.includes(value) ? value : null);
    if (value === "auto" || !value) store.set(KEY_FPS, null);
  }

  function watchFps(frames, info, onSlow, { warmup = 2500, window: span = 6000, min = 22 } = {}) {
    setTimeout(() => {
      if (document.visibilityState !== "visible") return;
      const f0 = frames(), t0 = performance.now();
      setTimeout(() => {
        if (document.visibilityState !== "visible") return;
        const fps = Math.round(((frames() - f0) * 1000) / (performance.now() - t0));
        if (fps >= min) return;
        store.set(KEY_FPS, JSON.stringify({ renderer: info.renderer, fps }));
        onSlow(fps);
      }, span);
    }, warmup);
  }

  const damp = (a, b, k, dt) => a + (b - a) * (1 - Math.exp(-k * dt));
  const rgb = (h) => { const n = parseInt(String(h).replace("#", ""), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
  const mix = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
  const css = (c, a) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
  const BLUE = [42, 141, 255], WHITE = [255, 255, 255];

  function geodesic(depth) {
    const t = (1 + Math.sqrt(5)) / 2;
    const norm = (v) => { const l = Math.hypot(v[0], v[1], v[2]); return [v[0] / l, v[1] / l, v[2] / l]; };
    const v = [[-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0], [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
               [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1]].map(norm);
    let faces = [[0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11], [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
                 [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9], [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1]];
    for (let d = 0; d < depth; d++) {
      const cache = new Map(), next = [];
      const mid = (a, b) => {
        const k = a < b ? `${a},${b}` : `${b},${a}`;
        if (!cache.has(k)) { v.push(norm([(v[a][0] + v[b][0]) / 2, (v[a][1] + v[b][1]) / 2, (v[a][2] + v[b][2]) / 2])); cache.set(k, v.length - 1); }
        return cache.get(k);
      };
      for (const [a, b, c] of faces) {
        const ab = mid(a, b), bc = mid(b, c), ca = mid(c, a);
        next.push([a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]);
      }
      faces = next;
    }
    const seen = new Set(), edges = [];
    for (const [a, b, c] of faces) for (const [x, y] of [[a, b], [b, c], [c, a]]) {
      const k = x < y ? x * 65536 + y : y * 65536 + x;
      if (!seen.has(k)) { seen.add(k); edges.push(x, y); }
    }
    return { verts: Float32Array.from(v.flat()), edges: Uint16Array.from(edges) };
  }

  class ThoughtCore {
    constructor(canvas) {
      this.c = canvas;
      this.ctx = canvas.getContext("2d");
      this.face = { listening: false, realAudio: false, thinking: false };
      this.color = rgb("#29e0ff"); this.target = this.color.slice();
      this.level = 0; this.levelTarget = 0; this.input = 0; this.speaking = false;
      this.mode = "face"; this.alpha = 0; this.layout = null;
      this.sphere = geodesic(2);
      this.proj = new Float32Array(this.sphere.verts.length);
      this.outer = new Float32Array(56); this.inner = new Float32Array(84);
      this.dust = Array.from({ length: 220 }, () => ({ a: Math.random() * Math.PI * 2, o: Math.random() - 0.5, z: Math.random() }));
      this.t = 0; this.last = 0; this.frames = 0;
      this.groove = 0; this.grooveTarget = 0; this.calm = 0; this.calmTarget = 0; this.burstT = 0;
      this._resize = this._resize.bind(this);
      global.addEventListener("resize", this._resize);
      this._resize();
      this._loop = this._loop.bind(this);
      this.raf = requestAnimationFrame(this._loop);
    }
    _resize() {
      const dpr = Math.min(1.5, global.devicePixelRatio || 1);
      const r = this.c.getBoundingClientRect();
      this.c.width = Math.max(1, r.width * dpr); this.c.height = Math.max(1, r.height * dpr);
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      this.w = r.width; this.h = r.height;
      this.layout = null;
    }
    setMode(mode) { this.mode = mode; }
    setStage(zone) { this.stage = zone; }
    setPresence(k) { this.presence = k; }
    setSpeaking(on, level = 1) { this.speaking = on; this.levelTarget = on ? level : 0; }
    setTint(hex) { this.target = rgb(hex); }
    setInputLevel(v) { this.input = Math.max(this.input, v); }
    setGroove(v) { this.grooveTarget = Math.max(this.grooveTarget * 0.6, Math.min(1, v)); }
    setCalm(on) { this.calmTarget = on ? 1 : 0; }
    burst() { this.burstT = 1; }
    destroy() { cancelAnimationFrame(this.raf); global.removeEventListener("resize", this._resize); }

    _target() {
      const t = this._place(), k = this.presence || 1;
      return { ...t, s: t.s * k };
    }
    _place() {
      const { w, h } = this, narrow = w < h;
      if (this.mode === "focus") return narrow ? { x: w / 2, y: h * 0.17, s: 0.34 } : { x: w * 0.13, y: h * 0.3, s: 0.42 };
      const z = this.stage;
      if (z) return { x: z.cx, y: z.cy, s: Math.max(0.26, Math.min(1, Math.min(z.w, z.h) * 0.42 / (Math.min(w, h) * 0.34))) };
      return { x: w / 2, y: h * 0.46, s: 1 };
    }
    _loop(ts) {
      this.raf = requestAnimationFrame(this._loop);
      const opacity = this.mode === "brain" ? 0 : 1;
      const active = this.speaking || this.face.listening || this.face.thinking || Math.abs(this.alpha - opacity) > 0.01
        || this.groove > 0.02 || this.burstT > 0.01;
      if (!active && ts - this.last < 32) return;
      const dt = Math.min(0.05, (ts - (this.last || ts)) / 1000);
      this.last = ts;
      this.alpha = damp(this.alpha, opacity, 4, dt);
      if (this.alpha < 0.005 && opacity === 0) {
        if (!this.cleared) { this.ctx.clearRect(0, 0, this.w, this.h); this.cleared = true; }
        return;
      }
      this.cleared = false;
      this.frames++;
      this.grooveTarget = damp(this.grooveTarget, 0, 2.5, dt);
      this.groove = damp(this.groove, this.grooveTarget, 12, dt);
      this.calm = damp(this.calm, this.calmTarget, 0.8, dt);
      this.burstT = damp(this.burstT, 0, 1.6, dt);
      this.t += dt * (this.face.thinking ? 2.2 : 1) * (1 + this.groove * 1.4) * (1 - this.calm * 0.55);
      for (let i = 0; i < 3; i++) this.color[i] += (this.target[i] - this.color[i]) * Math.min(1, dt * 3);
      const lv = !this.speaking ? 0 : this.face.realAudio ? this.levelTarget
        : this.levelTarget * (0.55 + 0.45 * Math.abs(Math.sin(this.t * 17) * Math.sin(this.t * 6.3)));
      this.level = damp(this.level, Math.min(1.2, lv), 18, dt);
      this.input = damp(this.input, 0, 6, dt);
      const tg = this._target();
      if (!this.layout) this.layout = { ...tg };
      for (const k of ["x", "y", "s"]) this.layout[k] = damp(this.layout[k], tg[k], 3.5, dt);
      if (window.jarvisPerf) window.jarvisPerf.measure("nucleo", () => this._draw(dt)); else this._draw(dt);
    }
    _draw(dt) {
      const { ctx, w, h, t, groove } = this, { x: cx0, y: cy0, s } = this.layout;
      const level = Math.max(this.level, groove * 0.85);
      const cx = cx0 + Math.sin(t * 3.1) * groove * w * 0.006, cy = cy0 + Math.abs(Math.sin(t * 6.2)) * groove * -h * 0.012;
      const R = Math.min(w, h) * 0.34 * s * (1 + groove * 0.035 * Math.sin(t * 12.4)), a = this.alpha * (1 - this.calm * 0.35);
      const hue = [0.5 + 0.5 * Math.sin(t * 1.3), 0.5 + 0.5 * Math.sin(t * 1.3 + 2.1), 0.5 + 0.5 * Math.sin(t * 1.3 + 4.2)].map((v) => v * 255);
      const tint = mix(this.color, hue, groove * 0.45), seg = mix(tint, BLUE, 0.45), core = mix(tint, WHITE, 0.55);
      const listen = this.face.listening ? this.input : 0;
      ctx.clearRect(0, 0, w, h);
      ctx.globalCompositeOperation = "lighter";

      const glow = ctx.createRadialGradient(cx, cy, R * 0.2, cx, cy, R * 1.7);
      glow.addColorStop(0, css(tint, (0.1 + level * 0.12 + listen * 0.1) * a));
      glow.addColorStop(1, css(tint, 0));
      ctx.fillStyle = glow;
      ctx.fillRect(cx - R * 1.7, cy - R * 1.7, R * 3.4, R * 3.4);

      const amp = 0.025 + level * 0.07 + listen * 0.05;
      const wave = (th, k) => R * (1.02 + amp * (Math.sin(3 * th + t * 0.7 + k) * 0.5 + Math.sin(5 * th - t * 1.1 + k * 2) * 0.3
        + Math.sin(9 * th + t * 2.3 + k) * (0.2 + level * 0.6)));
      ctx.lineWidth = 1;
      for (let k = 0; k < 3; k++) {
        ctx.strokeStyle = css(tint, (0.22 - k * 0.05) * a);
        ctx.beginPath();
        for (let i = 0; i <= 96; i++) {
          const th = (i / 96) * Math.PI * 2, r = wave(th, k) + k * R * 0.025;
          i ? ctx.lineTo(cx + Math.cos(th) * r, cy + Math.sin(th) * r) : ctx.moveTo(cx + Math.cos(th) * r, cy + Math.sin(th) * r);
        }
        ctx.stroke();
      }
      ctx.fillStyle = css(tint, 0.55 * a);
      for (const p of this.dust) {
        p.a += (0.04 + p.z * 0.05) * dt * (1 + level * 2);
        const r = wave(p.a, 0) + p.o * R * (0.08 + level * 0.08), sz = 0.8 + p.z * 1.4;
        ctx.fillRect(cx + Math.cos(p.a) * r, cy + Math.sin(p.a) * r, sz, sz);
      }

      const ring = (vals, r1, r2, rot, gain, color) => {
        const n = vals.length, gap = 0.012;
        for (let i = 0; i < n; i++) {
          const u = i / n;
          let v = 0.14 + 0.05 * Math.sin(t * 1.3 + i * 0.4);
          v += level * gain * (0.3 + 0.7 * (0.5 + 0.5 * Math.sin(i * 1.7 + t * 9)) * (0.5 + 0.5 * Math.sin(i * 0.37 - t * 4)));
          v += listen * (0.5 + 0.5 * Math.sin(i * 2.3 + t * 12)) * 0.9;
          if (this.face.thinking) { const d = (u - ((t * 0.35) % 1) + 1) % 1; v += Math.exp(-d * 12) * 0.8; }
          vals[i] = damp(vals[i], Math.min(1, v), 14, dt);
          const a0 = rot + u * Math.PI * 2 + gap, a1 = rot + ((i + 1) / n) * Math.PI * 2 - gap;
          const rr = r2 + (r2 - r1) * vals[i] * 0.25 * gain;
          ctx.fillStyle = css(color, (0.12 + vals[i] * 0.75) * a);
          ctx.beginPath(); ctx.arc(cx, cy, rr, a0, a1); ctx.arc(cx, cy, r1, a1, a0, true); ctx.fill();
        }
      };
      ring(this.outer, R * 0.66, R * 0.8, t * 0.05, 1, seg);
      ring(this.inner, R * 0.5, R * 0.58, -t * 0.08, 0.6, mix(seg, tint, 0.5));
      ctx.strokeStyle = css(seg, 0.18 * a);
      for (const r of [R * 0.47, R * 0.62, R * 0.84]) { ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke(); }

      const rs = R * 0.36 * (1 + level * 0.05 + listen * 0.04);
      ctx.globalCompositeOperation = "source-over";
      ctx.fillStyle = `rgba(0,14,20,${0.55 * a})`;
      ctx.beginPath(); ctx.arc(cx, cy, rs, 0, Math.PI * 2); ctx.fill();
      ctx.globalCompositeOperation = "lighter";
      const ry = t * 0.25, rx = 0.35 + Math.sin(t * 0.3) * 0.1;
      const cyA = Math.cos(ry), syA = Math.sin(ry), cxA = Math.cos(rx), sxA = Math.sin(rx);
      const V = this.sphere.verts, P = this.proj, E = this.sphere.edges;
      for (let i = 0; i < V.length; i += 3) {
        const x = V[i] * cyA + V[i + 2] * syA, z0 = -V[i] * syA + V[i + 2] * cyA;
        const y = V[i + 1] * cxA - z0 * sxA, z = V[i + 1] * sxA + z0 * cxA;
        P[i] = cx + x * rs; P[i + 1] = cy + y * rs; P[i + 2] = z;
      }
      for (const front of [false, true]) {
        ctx.strokeStyle = css(core, (front ? 0.5 + level * 0.3 : 0.1) * a);
        ctx.lineWidth = front ? 0.9 : 0.6;
        ctx.beginPath();
        for (let e = 0; e < E.length; e += 2) {
          const i = E[e] * 3, j = E[e + 1] * 3;
          if ((P[i + 2] + P[j + 2] > 0) !== front) continue;
          ctx.moveTo(P[i], P[i + 1]); ctx.lineTo(P[j], P[j + 1]);
        }
        ctx.stroke();
      }
      ctx.strokeStyle = css(WHITE, (0.75 + level * 0.25) * a);
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(cx, cy, rs, 0, Math.PI * 2); ctx.stroke();
      if (this.burstT > 0.01) {
        ctx.strokeStyle = css(mix(tint, WHITE, 0.3), this.burstT * 0.6 * a);
        ctx.lineWidth = 3 * this.burstT;
        ctx.beginPath(); ctx.arc(cx, cy, R * (0.9 + (1 - this.burstT) * 0.9), 0, Math.PI * 2); ctx.stroke();
      }
      ctx.globalCompositeOperation = "source-over";
    }
  }

  global.JarvisAvatar = { choose, probe, setDevicePref, watchFps, ThoughtCore, MODES };
})(window);
