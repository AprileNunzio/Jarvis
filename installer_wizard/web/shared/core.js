(function (global) {
  "use strict";

  function connectState(url, onState, onLink) {
    let es = null;
    let retry = null;
    let lastMsg = 0;
    function open() {
      es = new EventSource(url);
      es.onmessage = (ev) => {
        lastMsg = Date.now();
        onLink && onLink(true);
        try { onState(JSON.parse(ev.data)); } catch (e) { console.error(e); }
      };
      es.onerror = () => {
        onLink && onLink(false);
        es.close();
        clearTimeout(retry);
        retry = setTimeout(open, 2000);
      };
    }
    open();
    setInterval(() => {
      if (lastMsg && Date.now() - lastMsg > 25000) {
        lastMsg = 0; onLink && onLink(false); es && es.close(); open();
      }
    }, 5000);
  }

  const fmt = {
    bytes(n) {
      if (!n && n !== 0) return "—";
      const u = ["B", "KB", "MB", "GB", "TB"];
      let i = 0;
      while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
      return `${n.toFixed(n >= 100 || i === 0 ? 0 : 1)} ${u[i]}`;
    },
    rate(n) { return `${fmt.bytes(n)}/s`; },
    duration(s) {
      s = Math.max(0, Math.floor(s));
      const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
      if (d) return `${d}g ${h}h`;
      if (h) return `${h}h ${m}m`;
      if (m) return `${m}m ${s % 60}s`;
      return `${s}s`;
    },
    clock(d = new Date()) { return d.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit", second: "2-digit" }); },
    date(d = new Date()) { return d.toLocaleDateString("it-IT", { weekday: "long", day: "numeric", month: "long", year: "numeric" }); },
    esc(s) { return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); },
  };

  const PHASE_COLORS = {
    INSTALLING: [41, 224, 255], BOOTING: [61, 123, 255], UPDATING: [179, 107, 255],
    READY: [41, 224, 255], DEGRADED: [255, 181, 71], ERROR: [255, 77, 106],
  };

  class Reactor {
    constructor(canvas, opts = {}) {
      this.c = canvas;
      this.ctx = canvas.getContext("2d");
      this.progress = 0;
      this.shown = 0;
      this.color = [41, 224, 255];
      this.target = [41, 224, 255];
      this.activity = 0.4;
      this.level = 0;
      this.showRing = opts.ring !== false;
      this.particles = Array.from({ length: opts.particles || 90 }, () => this._particle());
      this.t = 0;
      this._resize = this._resize.bind(this);
      window.addEventListener("resize", this._resize);
      this._resize();
      requestAnimationFrame(this._frame.bind(this));
    }
    _particle() {
      return { a: Math.random() * Math.PI * 2, r: 0.55 + Math.random() * 0.45, s: (Math.random() * 0.4 + 0.1) * (Math.random() < 0.5 ? -1 : 1), z: Math.random() };
    }
    _resize() {
      const dpr = window.devicePixelRatio || 1;
      const rect = this.c.getBoundingClientRect();
      this.c.width = rect.width * dpr;
      this.c.height = rect.height * dpr;
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      this.w = rect.width; this.h = rect.height;
    }
    setPhase(phase) { this.target = PHASE_COLORS[phase] || this.target; }
    rgba(a) { const [r, g, b] = this.color; return `rgba(${r | 0},${g | 0},${b | 0},${a})`; }
    _frame(ts) {
      const dt = Math.min(0.05, (ts - (this.last || ts)) / 1000);
      this.last = ts;
      this.t += dt * (0.6 + this.activity * 1.6);
      this.shown += (this.progress - this.shown) * Math.min(1, dt * 3);
      for (let i = 0; i < 3; i++) this.color[i] += (this.target[i] - this.color[i]) * Math.min(1, dt * 2);

      const { ctx, w, h } = this;
      const cx = w / 2, cy = h / 2, R = Math.min(w, h) * 0.42;
      ctx.clearRect(0, 0, w, h);

      const pulse = 0.5 + 0.5 * Math.sin(this.t * 2.2) * (0.4 + this.activity * 0.6) + this.level * 0.8;
      const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * 1.25);
      glow.addColorStop(0, this.rgba(0.16 + pulse * 0.1));
      glow.addColorStop(0.5, this.rgba(0.05));
      glow.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = glow;
      ctx.fillRect(0, 0, w, h);

      for (const p of this.particles) {
        p.a += p.s * dt * (0.4 + this.activity);
        const rr = R * p.r * (1 + this.level * 0.08 * Math.sin(this.t * 9 + p.a * 3));
        const x = cx + Math.cos(p.a) * rr, y = cy + Math.sin(p.a) * rr * (0.94 + p.z * 0.06);
        ctx.fillStyle = this.rgba(0.25 + p.z * 0.6);
        ctx.beginPath(); ctx.arc(x, y, 0.6 + p.z * 1.4, 0, Math.PI * 2); ctx.fill();
      }

      ctx.lineCap = "round";
      const arcs = [
        [0.92, 1.2, 0.5, 6, 1.5], [0.8, -0.8, 0.35, 3, 3], [0.68, 1.6, 0.6, 12, 1], [0.56, -2.2, 0.25, 2, 4],
      ];
      for (const [rf, speed, alpha, segs, width] of arcs) {
        const rot = this.t * speed * 0.5;
        const gap = 0.35;
        for (let i = 0; i < segs; i++) {
          const a0 = rot + (i / segs) * Math.PI * 2;
          const a1 = a0 + (Math.PI * 2 / segs) * (1 - gap);
          ctx.strokeStyle = this.rgba(alpha);
          ctx.lineWidth = width;
          ctx.beginPath(); ctx.arc(cx, cy, R * rf, a0, a1); ctx.stroke();
        }
      }
      for (let i = 0; i < 120; i++) {
        const a = (i / 120) * Math.PI * 2;
        const long = i % 10 === 0;
        const r0 = R * 1.02, r1 = R * (long ? 1.08 : 1.05);
        ctx.strokeStyle = this.rgba(long ? 0.5 : 0.18);
        ctx.lineWidth = long ? 1.5 : 1;
        ctx.beginPath();
        ctx.moveTo(cx + Math.cos(a) * r0, cy + Math.sin(a) * r0);
        ctx.lineTo(cx + Math.cos(a) * r1, cy + Math.sin(a) * r1);
        ctx.stroke();
      }
      if (this.showRing) {
        ctx.strokeStyle = this.rgba(0.12);
        ctx.lineWidth = 6;
        ctx.beginPath(); ctx.arc(cx, cy, R * 1.0, 0, Math.PI * 2); ctx.stroke();
        const end = -Math.PI / 2 + (this.shown / 100) * Math.PI * 2;
        ctx.strokeStyle = this.rgba(0.95);
        ctx.shadowColor = this.rgba(0.9); ctx.shadowBlur = 18;
        ctx.lineWidth = 6;
        ctx.beginPath(); ctx.arc(cx, cy, R * 1.0, -Math.PI / 2, end); ctx.stroke();
        ctx.shadowBlur = 0;
      }
      const coreR = R * (0.3 + pulse * 0.025 + this.level * 0.06);
      const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR);
      core.addColorStop(0, "rgba(255,255,255,0.95)");
      core.addColorStop(0.25, this.rgba(0.85));
      core.addColorStop(0.7, this.rgba(0.18));
      core.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = core;
      ctx.beginPath(); ctx.arc(cx, cy, coreR, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = this.rgba(0.55);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      for (let i = 0; i <= 3; i++) {
        const a = -Math.PI / 2 + (i / 3) * Math.PI * 2 - this.t * 0.3;
        const x = cx + Math.cos(a) * R * 0.44, y = cy + Math.sin(a) * R * 0.44;
        i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      }
      ctx.stroke();

      requestAnimationFrame(this._frame.bind(this));
    }
  }

  global.Jarvis = { connectState, fmt, Reactor, PHASE_COLORS };
})(window);
