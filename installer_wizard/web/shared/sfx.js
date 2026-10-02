(() => {
  let ctx = null, master = null, fx = null, loopBus = null, ambBus = null, noiseBuf = null;
  let theme = "jarvis", volume = 0.55, fxLevel = 1, ambLevel = 0.18, ducked = false;
  const loops = {}, ambient = { kind: "none", nodes: [], timers: [] };

  function init() {
    if (ctx) { if (ctx.state === "suspended") ctx.resume(); return ctx; }
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    master = ctx.createGain(); master.gain.value = volume; master.connect(ctx.destination);
    fx = ctx.createGain(); fx.gain.value = fxLevel; fx.connect(master);
    loopBus = ctx.createGain(); loopBus.gain.value = 0.5; loopBus.connect(fx);
    ambBus = ctx.createGain(); ambBus.gain.value = ambLevel; ambBus.connect(master);
    noiseBuf = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate);
    const d = noiseBuf.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    return ctx;
  }

  const wave = () => (theme === "classic" ? "square" : theme === "soft" ? "sine" : "triangle");

  function tone(freq, start, dur, opts = {}) {
    const t0 = ctx.currentTime + start, o = ctx.createOscillator(), g = ctx.createGain();
    o.type = opts.type || wave();
    o.frequency.setValueAtTime(freq, t0);
    if (opts.to) o.frequency.exponentialRampToValueAtTime(opts.to, t0 + dur);
    if (opts.detune) o.detune.value = opts.detune;
    const peak = (opts.gain ?? 0.22) * (theme === "soft" ? 0.7 : theme === "classic" ? 0.45 : 1);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(peak, t0 + (opts.attack ?? 0.008));
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    let out = g;
    if (theme === "soft" || opts.lowpass) {
      const f = ctx.createBiquadFilter(); f.type = "lowpass"; f.frequency.value = opts.lowpass || 2400; g.connect(f); out = f;
    }
    o.connect(g); out.connect(opts.bus || fx);
    o.start(t0); o.stop(t0 + dur + 0.05);
    if (theme === "jarvis" && !opts.plain) {
      const s = ctx.createOscillator(), sg = ctx.createGain();
      s.type = "sine"; s.frequency.setValueAtTime(freq * 2, t0);
      if (opts.to) s.frequency.exponentialRampToValueAtTime(opts.to * 2, t0 + dur);
      sg.gain.setValueAtTime(0.0001, t0); sg.gain.exponentialRampToValueAtTime(peak * 0.25, t0 + 0.01);
      sg.gain.exponentialRampToValueAtTime(0.0001, t0 + dur * 0.8);
      s.connect(sg); sg.connect(opts.bus || fx); s.start(t0); s.stop(t0 + dur + 0.05);
    }
  }

  function noise(start, dur, opts = {}) {
    const t0 = ctx.currentTime + start, src = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain();
    src.buffer = noiseBuf; src.loop = true;
    f.type = opts.filter || "bandpass"; f.Q.value = opts.q ?? 1.2;
    f.frequency.setValueAtTime(opts.from || 800, t0);
    if (opts.to) f.frequency.exponentialRampToValueAtTime(opts.to, t0 + dur);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(opts.gain ?? 0.15, t0 + (opts.attack ?? dur * 0.3));
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    src.connect(f); f.connect(g); g.connect(opts.bus || fx);
    src.start(t0); src.stop(t0 + dur + 0.05);
  }

  const SOUNDS = {
    wake() { tone(420, 0, 0.32, { to: 1260, gain: 0.16 }); tone(1320, 0.18, 0.4, { gain: 0.1, plain: true }); },
    request() { tone(880, 0, 0.07, { gain: 0.14 }); tone(1320, 0.07, 0.09, { gain: 0.12 }); },
    done() { [660, 880, 1320].forEach((f, i) => tone(f, i * 0.07, 0.22, { gain: 0.12 })); },
    error() { tone(440, 0, 0.18, { gain: 0.16, type: "triangle" }); tone(311, 0.17, 0.32, { gain: 0.16, type: "triangle" }); },
    notify() { tone(1046, 0, 1.1, { gain: 0.16, type: "sine", attack: 0.004 }); tone(1568, 0, 0.8, { gain: 0.07, type: "sine", plain: true }); },
    reminder() { [0, 0.35, 0.7].forEach((s) => tone(988, s, 0.6, { gain: 0.12, type: "sine" })); },
    alert() { for (let i = 0; i < 6; i++) tone(i % 2 ? 660 : 880, i * 0.22, 0.2, { gain: 0.2, type: "square", lowpass: 3000, plain: true }); },
    doorbell() { tone(784, 0, 1.0, { gain: 0.2, type: "sine" }); tone(622, 0.55, 1.4, { gain: 0.2, type: "sine" }); },
    success() { [523, 659, 784, 1046, 1318].forEach((f, i) => tone(f, i * 0.06, 0.25, { gain: 0.1 })); },
    scan() { tone(300, 0, 1.0, { to: 2000, gain: 0.08, type: "sine" }); noise(0, 1.0, { from: 600, to: 5000, gain: 0.05 }); },
    powerup() { tone(110, 0, 1.2, { to: 880, gain: 0.14 }); noise(0, 1.2, { from: 200, to: 4000, gain: 0.06 }); },
    powerdown() { tone(880, 0, 1.0, { to: 90, gain: 0.14 }); noise(0, 1.0, { from: 4000, to: 200, gain: 0.05 }); },
    whoosh() { noise(0, 0.6, { from: 300, to: 3500, gain: 0.18, q: 0.8 }); },
    click() { tone(2200, 0, 0.03, { gain: 0.08, plain: true }); },
  };

  function startLoop(name) {
    if (loops[name]) return;
    const state = { timers: [], nodes: [] };
    loops[name] = state;
    if (name === "thinking") {
      [220, 330.5].forEach((f, i) => {
        const o = ctx.createOscillator(), g = ctx.createGain(), lfo = ctx.createOscillator(), lg = ctx.createGain();
        o.type = "sine"; o.frequency.value = f; o.detune.value = i ? 6 : -6;
        g.gain.value = 0.0; lfo.frequency.value = 0.7 + i * 0.13; lg.gain.value = 0.035;
        lfo.connect(lg); lg.connect(g.gain); o.connect(g); g.connect(loopBus);
        g.gain.setTargetAtTime(0.035, ctx.currentTime, 0.4);
        o.start(); lfo.start(); state.nodes.push(o, lfo, g);
      });
    } else if (name === "working") {
      const scale = [523, 587, 659, 784, 880, 1046, 1175];
      const tick = () => {
        if (!loops[name]) return;
        tone(scale[Math.floor(Math.random() * scale.length)] * (Math.random() < 0.3 ? 2 : 1), 0, 0.05, { gain: 0.045, bus: loopBus, plain: true });
        state.timers.push(setTimeout(tick, 90 + Math.random() * 160));
      };
      tick();
    }
  }

  function stopLoop(name) {
    const state = loops[name];
    if (!state) return;
    delete loops[name];
    state.timers.forEach(clearTimeout);
    state.nodes.forEach((n) => {
      if (n.gain) n.gain.setTargetAtTime(0, ctx.currentTime, 0.15);
      else setTimeout(() => { try { n.stop(); } catch (e) { } }, 600);
    });
  }

  function stopAmbient() {
    ambient.timers.forEach(clearTimeout); ambient.timers = [];
    ambient.nodes.forEach((n) => { if (n.gain) n.gain.setTargetAtTime(0, ctx.currentTime, 0.6); else setTimeout(() => { try { n.stop(); } catch (e) { } }, 2500); });
    ambient.nodes = []; ambient.kind = "none";
  }

  function osc(f, type, gain, bus, detune = 0) {
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type = type; o.frequency.value = f; o.detune.value = detune; g.gain.value = 0;
    g.gain.setTargetAtTime(gain, ctx.currentTime, 1.5);
    o.connect(g); g.connect(bus); o.start(); ambient.nodes.push(o, g);
    return { o, g };
  }

  function noiseBed(type, freq, q, gain, lfoRate = 0) {
    const src = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain();
    src.buffer = noiseBuf; src.loop = true; f.type = type; f.frequency.value = freq; f.Q.value = q;
    g.gain.value = 0; g.gain.setTargetAtTime(gain, ctx.currentTime, 1.5);
    src.connect(f); f.connect(g); g.connect(ambBus); src.start(); ambient.nodes.push(src, g);
    if (lfoRate) {
      const l = ctx.createOscillator(), lg = ctx.createGain();
      l.frequency.value = lfoRate; lg.gain.value = gain * 0.8; l.connect(lg); lg.connect(g.gain); l.start(); ambient.nodes.push(l);
    }
  }

  function setAmbient(kind) {
    if (kind === ambient.kind) return;
    stopAmbient();
    if (!kind || kind === "none") return;
    ambient.kind = kind;
    if (kind === "reactor") { osc(55, "sine", 0.25, ambBus); osc(110, "sine", 0.12, ambBus, 4); osc(165, "triangle", 0.03, ambBus); noiseBed("bandpass", 1800, 0.7, 0.03); }
    if (kind === "space") { [110, 164.8, 220, 329.6].forEach((f, i) => osc(f, "sine", 0.06, ambBus, (i - 1.5) * 7)); noiseBed("lowpass", 400, 0.5, 0.04, 0.05); }
    if (kind === "rain") {
      noiseBed("bandpass", 2400, 0.6, 0.18); noiseBed("lowpass", 500, 0.5, 0.08);
      const drop = () => { if (ambient.kind !== "rain") return; tone(1800 + Math.random() * 2400, 0, 0.04, { gain: 0.03, bus: ambBus, type: "sine", plain: true }); ambient.timers.push(setTimeout(drop, 40 + Math.random() * 260)); };
      drop();
    }
    if (kind === "ocean") { noiseBed("lowpass", 700, 0.4, 0.22, 0.09); noiseBed("bandpass", 2000, 0.5, 0.04, 0.07); }
    if (kind === "lab") {
      osc(60, "sine", 0.12, ambBus); osc(120, "sine", 0.05, ambBus); noiseBed("highpass", 6000, 0.3, 0.015);
      const bleep = () => { if (ambient.kind !== "lab") return; tone(1200 + Math.random() * 1600, 0, 0.06, { gain: 0.025, bus: ambBus, plain: true }); ambient.timers.push(setTimeout(bleep, 2500 + Math.random() * 6000)); };
      bleep();
    }
  }

  window.JarvisSfx = {
    names: () => Object.keys(SOUNDS).concat(["thinking", "working"]),
    play(name) {
      if (!init()) return;
      if (name === "thinking" || name === "working") { startLoop(name); setTimeout(() => stopLoop(name), 2500); return; }
      if (SOUNDS[name]) SOUNDS[name]();
    },
    loop(name, on) { if (!init()) return; on ? startLoop(name) : stopLoop(name); },
    stopLoops() { Object.keys(loops).forEach(stopLoop); },
    ambient(kind, level) {
      if (!init()) return;
      if (level != null) { ambLevel = level; ambBus.gain.setTargetAtTime(ducked ? ambLevel * 0.25 : ambLevel, ctx.currentTime, 0.4); }
      setAmbient(kind);
    },
    configure(opts = {}) {
      if (!init()) return;
      if (opts.theme) theme = opts.theme;
      if (opts.volume != null) { volume = opts.volume; master.gain.setTargetAtTime(volume, ctx.currentTime, 0.2); }
      if (opts.effects != null) { fxLevel = opts.effects; fx.gain.setTargetAtTime(fxLevel, ctx.currentTime, 0.2); }
    },
    duck(on) {
      if (!ctx || ducked === on) return;
      ducked = on;
      ambBus.gain.setTargetAtTime(on ? ambLevel * 0.25 : ambLevel, ctx.currentTime, 0.3);
      loopBus.gain.setTargetAtTime(on ? 0.15 : 0.5, ctx.currentTime, 0.2);
    },
  };
})();
