(() => {
  const D = window.JarvisDisplay, { $ } = D;

  const Voice = (() => {
    let ctx = null, gain = null, volume = 1, analyser = null, samples = null, spectrum = null, source = null, generation = 0, active = false, raf = 0;

    function ensure() {
      if (!ctx) {
        ctx = new (window.AudioContext || window.webkitAudioContext)();
        analyser = ctx.createAnalyser();
        analyser.fftSize = 1024;
        analyser.smoothingTimeConstant = 0.35;
        gain = ctx.createGain();
        gain.gain.value = volume;
        analyser.connect(gain);
        gain.connect(ctx.destination);
        samples = new Float32Array(analyser.fftSize);
        spectrum = new Uint8Array(analyser.frequencyBinCount);
      }
      if (ctx.state === "suspended") ctx.resume();
    }

    function sentences(text) {
      const parts = text.replace(/\s+/g, " ").match(/[^.!?;:]+[.!?;:]*/g) || [text];
      const out = [];
      for (const p of parts.map((x) => x.trim()).filter(Boolean)) {
        if (out.length > 1 && (out[out.length - 1].length < 40 || p.length < 12)) out[out.length - 1] += " " + p;
        else out.push(p);
      }
      if (out.length && out[0].length > 70) {
        const cut = out[0].indexOf(",", 20);
        if (cut > 0 && cut < out[0].length - 15) out.splice(0, 1, out[0].slice(0, cut + 1), out[0].slice(cut + 1).trim());
      }
      return out;
    }

    async function synth(text, lang) {
      const r = await fetch("/api/assistant/tts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, lang }) });
      if (!r.ok) throw new Error(`TTS ${r.status}`);
      return ctx.decodeAudioData(await r.arrayBuffer());
    }

    function play(buffer, gen) {
      return new Promise((resolve) => {
        if (gen !== generation) return resolve();
        source = ctx.createBufferSource();
        source.buffer = buffer;
        source.connect(analyser);
        source.onended = resolve;
        source.start();
      });
    }

    function level() {
      analyser.getFloatTimeDomainData(samples);
      let sum = 0;
      for (let i = 0; i < samples.length; i++) sum += samples[i] * samples[i];
      return Math.min(1.4, Math.sqrt(sum / samples.length) * 7);
    }

    function bands() {
      analyser.getByteFrequencyData(spectrum);
      const hz = ctx.sampleRate / analyser.fftSize;
      const sum = (a, b) => {
        let s = 0; const i0 = Math.floor(a / hz), i1 = Math.min(spectrum.length - 1, Math.ceil(b / hz));
        for (let i = i0; i <= i1; i++) s += spectrum[i];
        return s / Math.max(1, i1 - i0 + 1) / 255;
      };
      return { low: sum(250, 900), mid: sum(1000, 2600), high: sum(3500, 8000) };
    }

    function animate() {
      const l = level();
      if (D.avatar) { D.avatar.setSpeaking(true, l); if (D.avatar.setVoice) D.avatar.setVoice(bands()); }
      raf = requestAnimationFrame(animate);
    }

    function quiet() {
      active = false; cancelAnimationFrame(raf);
      if (D.avatar) { D.avatar.setSpeaking(false); if (D.avatar.face) D.avatar.face.realAudio = false; }
    }

    async function speak(text, lang) {
      const gen = ++generation;
      ensure();
      const parts = sentences(text);
      active = true;
      if (D.avatar && D.avatar.face) D.avatar.face.realAudio = true;
      cancelAnimationFrame(raf); animate();
      try {
        let next = synth(parts[0], lang);
        for (let i = 0; i < parts.length; i++) {
          const buffer = await next;
          if (gen !== generation) return;
          if (i + 1 < parts.length) next = synth(parts[i + 1], lang);
          await play(buffer, gen);
        }
      } finally {
        if (gen === generation) quiet();
      }
    }

    function stop() {
      generation++;
      try { source && source.stop(); } catch (e) {}
      quiet();
    }

    function setVolume(v) { volume = Math.max(0, Math.min(1, v)); if (gain) gain.gain.setTargetAtTime(volume, ctx.currentTime, 0.2); }

    return { speak, stop, setVolume, isSpeaking: () => active };
  })();

  function systemSpeak(text, lang) {
    if (!("speechSynthesis" in window)) return false;
    const it = speechSynthesis.getVoices().find((v) => v.lang && v.lang.toLowerCase().startsWith(lang || "it"));
    if (!it) return false;
    const u = new SpeechSynthesisUtterance(text.replace(/[*#_`]/g, ""));
    u.voice = it; u.lang = it.lang; u.rate = 1.0;
    u.onstart = () => D.avatar && D.avatar.setSpeaking(true, 1);
    u.onend = u.onerror = () => D.avatar && D.avatar.setSpeaking(false);
    speechSynthesis.cancel(); speechSynthesis.speak(u);
    return true;
  }

  function mouthOnly(text) {
    if (!D.avatar) return;
    D.avatar.setSpeaking(true, 1);
    setTimeout(() => D.avatar.setSpeaking(false), Math.min(12000, 60 * text.length));
  }

  D.speak = async (text, lang) => {
    D.Ear.speaking(true);
    if (D.avatar && D.avatar.direct) D.avatar.direct(text || "");
    try {
      if (!D.voiceOn || !text) { mouthOnly(text || ""); return; }
      try { await Voice.speak(text, lang); }
      catch (err) {
        console.warn("Voce neurale non disponibile:", err);
        if (!systemSpeak(text, lang)) mouthOnly(text);
      }
    } finally {
      setTimeout(() => { D.Ear.speaking(false); if (D.lastVoice) { D.lastVoice = false; D.Ear.followup(); } }, 350);
    }
  };

  D.setVoiceVolume = (v) => Voice.setVolume(v);

  D.hush = () => { D.lastVoice = false; Voice.stop(); if ("speechSynthesis" in window) speechSynthesis.cancel(); };

  D.isSpeaking = () => Voice.isSpeaking() || ("speechSynthesis" in window && speechSynthesis.speaking);

  D.startVoiceToggle = () => {
    $("btn-voice").classList.toggle("on", D.voiceOn);
    $("btn-voice").addEventListener("click", () => {
      D.voiceOn = !D.voiceOn; $("btn-voice").classList.toggle("on", D.voiceOn);
      if (!D.voiceOn) { Voice.stop(); if ("speechSynthesis" in window) speechSynthesis.cancel(); }
    });
  };
})();
