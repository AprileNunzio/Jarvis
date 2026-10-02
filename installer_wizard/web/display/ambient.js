(() => {
  const D = window.JarvisDisplay;
  const REDUCED = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  const SCENES = {
    clear: { stars: 1, sun: 1 }, partly: { clouds: 5, stars: 0.5, sun: 0.6 }, cloudy: { clouds: 9 },
    fog: { clouds: 6, fog: 1 }, drizzle: { clouds: 7, rain: 90 }, rain: { clouds: 9, rain: 220 },
    snow: { clouds: 6, snow: 140 }, storm: { clouds: 10, rain: 300, flash: 1 },
  };
  let canvas, ctx, w = 0, h = 0, scene = {}, day = true, wind = 0, parts = [], clouds = [], stars = [], flash = 0, last = 0;

  function resize() {
    const dpr = Math.min(1.25, window.devicePixelRatio || 1);
    w = window.innerWidth; h = window.innerHeight;
    canvas.width = w * dpr; canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function build() {
    const scale = D.look && D.look.mode === "light" ? 0.6 : 1;
    const n = Math.round((scene.rain || scene.snow || 0) * scale);
    parts = Array.from({ length: n }, () => ({ x: Math.random() * w, y: Math.random() * h, v: 0.6 + Math.random() * 0.8, z: Math.random() }));
    clouds = Array.from({ length: scene.clouds || 0 }, (_, i) => ({ x: Math.random() * w, y: h * (0.05 + Math.random() * 0.4),
      r: 120 + Math.random() * 220, v: 4 + Math.random() * 8, a: 0.03 + Math.random() * 0.04, i }));
    stars = Array.from({ length: !day && scene.stars ? Math.round(120 * scene.stars) : 0 }, () => ({ x: Math.random() * w, y: Math.random() * h * 0.7,
      s: Math.random() * 1.4 + 0.3, p: Math.random() * Math.PI * 2 }));
  }

  function draw(ts) {
    requestAnimationFrame(draw);
    if (ts - last < 33) return;
    const dt = Math.min(0.1, (ts - last) / 1000); last = ts;
    if (window.jarvisPerf) window.jarvisPerf.measure("meteo", () => paint(ts, dt)); else paint(ts, dt);
  }

  function paint(ts, dt) {
    ctx.clearRect(0, 0, w, h);
    if (D.mode === "brain") return;
    if (day && scene.sun) {
      const g = ctx.createRadialGradient(w * 0.82, -h * 0.1, 10, w * 0.82, -h * 0.1, h * 0.9);
      g.addColorStop(0, `rgba(255,197,61,${0.12 * scene.sun})`); g.addColorStop(1, "rgba(255,197,61,0)");
      ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
    }
    for (const s of stars) {
      s.p += dt * 1.5;
      ctx.fillStyle = `rgba(217,243,255,${0.25 + 0.35 * Math.sin(s.p) ** 2})`;
      ctx.fillRect(s.x, s.y, s.s, s.s);
    }
    for (const c of clouds) {
      c.x += (c.v + wind * 0.3) * dt;
      if (c.x - c.r > w) c.x = -c.r;
      const g = ctx.createRadialGradient(c.x, c.y, 0, c.x, c.y, c.r);
      const tone = scene.flash ? "90,100,130" : day ? "200,225,240" : "120,150,180";
      g.addColorStop(0, `rgba(${tone},${c.a})`); g.addColorStop(1, `rgba(${tone},0)`);
      ctx.fillStyle = g; ctx.beginPath(); ctx.ellipse(c.x, c.y, c.r * 1.6, c.r * 0.6, 0, 0, Math.PI * 2); ctx.fill();
    }
    if (scene.fog) { ctx.fillStyle = "rgba(160,190,210,0.05)"; ctx.fillRect(0, h * 0.45, w, h * 0.55); }
    const slant = Math.min(0.6, wind / 60);
    if (scene.rain) {
      ctx.strokeStyle = "rgba(120,190,255,0.28)"; ctx.lineWidth = 1; ctx.beginPath();
      for (const p of parts) {
        const len = 10 + p.z * 16;
        p.y += (620 + p.z * 520) * p.v * dt; p.x += slant * 400 * dt;
        if (p.y > h) { p.y = -len; p.x = Math.random() * w; }
        ctx.moveTo(p.x, p.y); ctx.lineTo(p.x - slant * len, p.y - len);
      }
      ctx.stroke();
    }
    if (scene.snow) {
      ctx.fillStyle = "rgba(235,245,255,0.7)";
      for (const p of parts) {
        p.y += (30 + p.z * 50) * p.v * dt; p.x += Math.sin(ts / 900 + p.z * 9) * 0.4 + slant;
        if (p.y > h) { p.y = -4; p.x = Math.random() * w; }
        ctx.beginPath(); ctx.arc(p.x, p.y, 1 + p.z * 2, 0, Math.PI * 2); ctx.fill();
      }
    }
    if (scene.flash) {
      if (flash <= 0 && Math.random() < dt * 0.12) flash = 1;
      if (flash > 0) {
        ctx.fillStyle = `rgba(210,225,255,${0.18 * flash * (Math.random() > 0.3 ? 1 : 0.3)})`; ctx.fillRect(0, 0, w, h);
        flash -= dt * 2.5;
      }
    }
  }

  async function refresh() {
    try {
      const d = await fetch("/api/ambient").then((r) => r.json());
      const next = SCENES[d.icon] || {};
      const changed = JSON.stringify(next) !== JSON.stringify(scene) || d.day !== day;
      scene = next; day = d.day !== false; wind = Number(d.wind) || 0;
      document.body.dataset.weather = d.icon || "";
      if (changed) build();
    } catch (err) {
      console.info("Meteo di sfondo non disponibile", err);
    }
  }

  D.startAmbient = () => {
    if (REDUCED) return;
    canvas = document.createElement("canvas");
    canvas.id = "ambient";
    document.body.prepend(canvas);
    ctx = canvas.getContext("2d");
    resize();
    window.addEventListener("resize", () => { resize(); build(); });
    refresh();
    setInterval(refresh, 10 * 60000);
    requestAnimationFrame(draw);
  };
})();
