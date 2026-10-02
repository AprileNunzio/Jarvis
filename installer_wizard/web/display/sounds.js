(() => {
  const D = window.JarvisDisplay, S = window.JarvisSfx;
  const THINK_AFTER = 700, WORK_AFTER = 5000, URGENT = ["alert", "doorbell"];
  const NOTIFY = { alert_error: "alert", alarm: "alert", reminder: "reminder", alert_warning: "notify", notice: "notify", g_notify: "notify", alert_info: "notify" };
  let cfg = null, seenCues = new Set(), seenDesk = null, earState = "idle", timers = [];

  const on = () => cfg && cfg.enabled;
  const muted = () => cfg && cfg.level === "mute";
  const allowed = (cat) => on() && !muted() && (cat !== "feedback" || cfg.feedback) && (cat !== "thinking" || cfg.thinking) && (cat !== "notify" || cfg.notify);

  function play(name, cat, force) {
    if (!S) return;
    if (!force && !allowed(cat) && !(URGENT.includes(name) && on())) return;
    try { S.play(name); } catch (err) { }
  }

  function apply() {
    if (!S || !cfg) return;
    try {
      const quietFx = cfg.quiet ? (cfg.quiet_effects || 25) / 100 : 1;
      S.configure({ theme: cfg.theme, volume: on() ? (cfg.volume || 55) / 100 : 0, effects: muted() ? 0 : quietFx });
      S.ambient(on() && !cfg.quiet ? cfg.ambient : "none", (cfg.ambient_volume || 18) / 100);
      if (D.setVoiceVolume) D.setVoiceVolume(cfg.quiet ? (cfg.quiet_voice || 45) / 100 : 1);
    } catch (err) { }
  }

  function clearTimers() { timers.forEach(clearTimeout); timers = []; if (S) S.stopLoops(); }

  function wrapAsk() {
    const ask = D.ask;
    if (!ask || ask._sounds) return;
    D.ask = async (...args) => {
      play("request", "feedback");
      clearTimers();
      timers.push(setTimeout(() => allowed("thinking") && S.loop("thinking", true), THINK_AFTER));
      timers.push(setTimeout(() => { if (allowed("thinking")) { S.loop("thinking", false); S.loop("working", true); } }, WORK_AFTER));
      try { return await ask(...args); }
      finally {
        clearTimers();
        const say = document.getElementById("say");
        if (say && say.textContent.startsWith("⚠")) play("error", "feedback");
      }
    };
    D.ask._sounds = true;
  }

  function wrapSpeak() {
    const speak = D.speak;
    if (!speak || speak._sounds) return;
    D.speak = async (...args) => {
      clearTimers();
      if (S) S.duck(true);
      try { return await speak(...args); }
      finally { if (S && earState !== "listening") S.duck(false); }
    };
    D.speak._sounds = true;
  }

  window.addEventListener("jarvis-ear", (e) => {
    const s = e.detail.state;
    if (s === "listening" && earState !== "listening" && !D.busy) play("wake", "feedback");
    earState = s;
    if (S) S.duck(s === "listening" || s === "transcribing" || (D.isSpeaking && D.isSpeaking()));
  });

  D.Sounds = {
    update(state) {
      if (!state) return;
      const before = JSON.stringify(cfg && { ...cfg, cues: 0 });
      cfg = state;
      if (JSON.stringify({ ...cfg, cues: 0 }) !== before) apply();
      for (const c of state.cues || []) {
        if (seenCues.has(c.id)) continue;
        seenCues.add(c.id);
        if (Date.now() / 1000 - c.at < 8) play(c.name, "cue", c.force);
      }
      if (seenCues.size > 200) seenCues = new Set([...seenCues].slice(-50));
    },
    desk(list) {
      const keys = new Map((list || []).map((i) => [i.key, i.id]));
      if (seenDesk) {
        for (const [key, id] of keys) {
          if (!seenDesk.has(key) && NOTIFY[id]) { play(NOTIFY[id], NOTIFY[id] === "alert" ? "cue" : "notify"); break; }
        }
      }
      seenDesk = new Set(keys.keys());
    },
    play: (name) => play(name, "cue", true),
  };

  D.startSounds = () => { wrapAsk(); wrapSpeak(); };
})();
