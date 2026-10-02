(() => {
  const WINDOW = 10000, JANK = 50, SLOW_P95 = 40, SLOW_ROUNDS = 2;
  const st = { frames: [], longs: 0, longMs: 0, last: 0, start: performance.now(), slow: 0, summary: "misura in corso", lite: "", costs: {} };

  function gpu() {
    try {
      const gl = document.createElement("canvas").getContext("webgl");
      const ext = gl && gl.getExtension("WEBGL_debug_renderer_info");
      const name = ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl ? "webgl" : "nessuna";
      return String(name).replace(/^ANGLE \(|\)$/g, "").replace(/\s*\(0x[0-9a-f]+\)|Direct3D11.*|vs_\d.*$/gi, "").slice(0, 60).trim();
    } catch (err) { return "?"; }
  }
  const GPU = gpu();

  function lite(reason) {
    if (document.body.classList.contains("lite")) return;
    document.body.classList.add("lite");
    st.lite = reason;
    console.warn(`Display lento (${reason}): tolgo sfocature ed effetti pesanti`);
  }

  function frame(now) {
    requestAnimationFrame(frame);
    if (st.last && !document.hidden) st.frames.push(now - st.last);
    st.last = now;
  }

  function round() {
    const f = st.frames.splice(0).sort((a, b) => a - b);
    const look = (window.JarvisDisplay && window.JarvisDisplay.look) || {};
    const mode = window.jarvisScene && window.JarvisDisplay.avatar === window.jarvisScene ? "3d" : look.mode || "?";
    if (f.length < 10) { st.summary = `fermo (scheda nascosta) modo=${mode} gpu=${GPU}`; st.longs = st.longMs = 0; return; }
    const avg = f.reduce((a, b) => a + b, 0) / f.length, p95 = f[Math.floor(f.length * 0.95)];
    const janks = f.filter((x) => x > JANK).length;
    st.summary = `fps=${Math.round(1000 / avg)} p95=${Math.round(p95)}ms scatti=${janks} lunghi=${st.longs}/${Math.round(st.longMs)}ms`
      + ` modo=${mode} gpu=${GPU} dpr=${window.devicePixelRatio}${st.lite ? " leggero=" + st.lite : ""}`;
    const top = Object.entries(st.costs).sort((a, b) => b[1] - a[1]).slice(0, 4).map(([k, v]) => `${k}:${Math.round(v)}`).join(",");
    if (top) st.summary += ` costi_ms=${top}`;
    if (window.jarvisHands) st.summary += ` mani=«${window.jarvisHands.status}»`;
    st.costs = {};
    st.longs = st.longMs = 0;
    st.slow = p95 > SLOW_P95 || janks > 20 ? st.slow + 1 : 0;
    if (st.slow >= SLOW_ROUNDS) lite(`p95 ${Math.round(p95)}ms`);
  }

  try {
    new PerformanceObserver((list) => list.getEntries().forEach((e) => { st.longs++; st.longMs += e.duration; }))
      .observe({ type: "longtask", buffered: false });
  } catch (err) { }
  requestAnimationFrame(frame);
  setInterval(round, WINDOW);
  const cost = (name, ms) => { st.costs[name] = (st.costs[name] || 0) + ms; };
  const measure = (name, fn) => { const t0 = performance.now(); try { return fn(); } finally { cost(name, performance.now() - t0); } };
  window.jarvisPerf = { get text() { return st.summary; }, lite, gpu: GPU, cost, measure };
})();
