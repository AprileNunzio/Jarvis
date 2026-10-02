(function (J) {
  "use strict";
  const { damp } = J;
  const H = (J.Holo = J.Holo || {});
  const ease = (x) => x * x * (3 - 2 * x);

  function blankPose() {
    return { rx: 0, ry: 0, rz: 0, px: 0, py: 0, breath: 1, lookX: 0, lookY: 0, morph: {} };
  }

  function sample(keys, t) {
    if (keys.length === 1 || t <= keys[0][0]) return keys[0][1];
    for (let i = 1; i < keys.length; i++) {
      const [t1, v1] = keys[i];
      if (t <= t1) {
        const [t0, v0] = keys[i - 1];
        return v0 + (v1 - v0) * ease((t - t0) / Math.max(1e-4, t1 - t0));
      }
    }
    return keys[keys.length - 1][1];
  }

  class Animator {
    constructor(onEvent) {
      this.onEvent = onEvent || (() => {});
      this.layers = { macro: [], micro: [] };
      this.emo = { cur: {}, target: {}, until: 0 };
      this.nextBlink = 0; this.nextMicro = 4;
      this.nod = 0; this.nodVel = 0; this.lastJaw = 0; this.nextNod = 0;
      this.tilt = 0; this.reveal = 0;
    }

    play(name, weight = 1) {
      const found = H.Library.find(name);
      if (!found) return false;
      const { key, clip } = found, list = this.layers[clip.layer];
      if (clip.layer === "macro") list.forEach((it) => (it.stopping = true));
      list.push({ key, clip, t: 0, w: clip.fade ? 0 : 1, weight, stopping: false, fired: 0 });
      return true;
    }

    stop(name) {
      const k = name ? (H.Library.find(name) || { key: name }).key : null;
      for (const list of Object.values(this.layers)) list.forEach((it) => { if (!k || it.key === k) it.stopping = true; });
    }

    playing(name) {
      return this.layers.macro.some((it) => it.key === name && !it.stopping);
    }

    express(name, seconds = 2.5) {
      const e = H.Library.emotion(name);
      if (!e) return false;
      this.emo.target = { ...e.pose };
      this.emo.until = e.key === "neutral" ? 0 : Date.now() + seconds * 1000;
      return true;
    }

    _base(t, dt, st, p, look) {
      const g = st.groove, joy = st.joy, mo = 1 - st.calm * 0.6;
      const busy = this.layers.macro.some((it) => !it.stopping) || Math.abs(this.emo.cur.ry || 0) > 0.02;
      const quiet = !(st.speaking || st.listening || look.following || busy);
      this.reveal = damp(this.reveal, quiet ? Math.sin(t * 0.09) * 0.45 * (1 - g) : 0, 1.2, dt);
      if (st.speaking && st.jaw > 0.8 && this.lastJaw <= 0.8 && t > this.nextNod) {
        this.nodVel += 0.7 + Math.random() * 0.5;
        this.nextNod = t + 0.45 + Math.random() * 0.6;
      }
      this.lastJaw = st.jaw;
      this.nodVel += (-this.nod * 60 - this.nodVel * 9) * dt;
      this.nod += this.nodVel * dt;
      this.tilt = damp(this.tilt, st.listening ? 0.08 : st.speaking ? Math.sin(t * 0.7) * 0.035 : 0, 2.5, dt);
      p.ry = look.x * 0.7 + Math.sin(t * 0.31) * 0.1 * mo + Math.sin(t * 3.1) * g * 0.14 + this.reveal;
      p.rx = -look.y * 0.7 + Math.sin(t * 0.23) * 0.04 * mo + (st.speaking ? Math.sin(t * 5.1) * 0.012 : 0) + this.nod - joy * 0.08;
      p.rz = Math.sin(t * 0.19) * 0.02 + this.tilt + Math.sin(t * 6.2) * g * 0.1;
      p.px = Math.sin(t * 3.1) * g * 0.06;
      p.py = Math.abs(Math.sin(t * 6.2)) * g * 0.08 + joy * 0.05;
      p.breath = 1 + Math.sin(t * 1.3) * 0.006 * mo + g * 0.03 * Math.sin(t * 12.4) + joy * 0.06;
      p.lookX = look.x; p.lookY = look.y;
      p.morph.mouthSmile = joy * 0.6 + g * 0.3;
    }

    _auto(t, st) {
      if (t > this.nextBlink) {
        this.play("blink");
        this.nextBlink = t + (st.thinking ? 1.5 : 2) + Math.random() * 4;
      }
      if (t > this.nextMicro) {
        const pick = st.speaking ? (Math.random() < 0.5 ? "sopracciglio" : "annuisce_lieve") : st.listening ? "annuisce_lieve" : "microsorriso";
        if (!st.calm || st.calm < 0.5) this.play(pick, 0.8);
        this.nextMicro = t + 6 + Math.random() * 10;
      }
    }

    _emotion(dt, p) {
      const e = this.emo;
      if (e.until && Date.now() > e.until) { e.target = {}; e.until = 0; }
      const keys = new Set([...Object.keys(e.cur), ...Object.keys(e.target)]);
      for (const k of keys) {
        const v = (e.cur[k] = damp(e.cur[k] || 0, e.target[k] || 0, 4, dt));
        if (H.Library.HEAD.has(k)) p[k] += v; else p.morph[k] = (p.morph[k] || 0) + v;
      }
    }

    _layer(list, dt, p) {
      for (let i = list.length - 1; i >= 0; i--) {
        const it = list[i], c = it.clip;
        it.t += dt;
        it.w = it.stopping ? (c.fade ? it.w - dt / c.fade : 0) : (c.fade ? Math.min(1, it.w + dt / c.fade) : 1);
        if ((it.stopping && it.w <= 0) || (!c.loop && it.t >= c.dur)) { list.splice(i, 1); continue; }
        const events = c.events || [];
        while (it.fired < events.length && it.t >= events[it.fired][0]) { this.onEvent(events[it.fired][1], events[it.fired][2]); it.fired++; }
        const w = it.w * it.weight, tt = c.loop && c.dur ? it.t % c.dur : it.t;
        for (const ch in c.tracks) this._add(p, ch, sample(c.tracks[ch], tt) * w);
        for (const ch in c.osc || {}) {
          const [amp, freq, phase, abs] = c.osc[ch], s = Math.sin(it.t * freq + phase);
          this._add(p, ch, amp * (abs ? Math.abs(s) : s) * w);
        }
      }
    }

    _add(p, ch, v) {
      if (H.Library.HEAD.has(ch)) p[ch] += v; else p.morph[ch] = (p.morph[ch] || 0) + v;
    }

    update(t, dt, st, p, look) {
      for (const k in p.morph) p.morph[k] = 0;
      this._base(t, dt, st, p, look);
      this._auto(t, st);
      this._emotion(dt, p);
      this._layer(this.layers.macro, dt, p);
      this._layer(this.layers.micro, dt, p);
    }

    finish(p, calm) {
      const m = p.morph;
      m.eyeOpen = Math.max(0, Math.min(1.3, (1 - (m.eyeBlink || 0) - (m.eyeSquint || 0) * 0.4 + (m.eyeWide || 0) * 0.3) * (1 - (calm || 0) * 0.45)));
      for (const k in p.morph) p.morph[k] = Math.max(-0.2, Math.min(1, p.morph[k]));
    }
  }

  H.Animator = Animator;
  H.blankPose = blankPose;
})(window.Jarvis3D);
