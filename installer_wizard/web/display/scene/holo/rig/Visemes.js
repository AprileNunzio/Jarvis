(function (J) {
  "use strict";
  const { damp } = J;
  const H = (J.Holo = J.Holo || {});
  const SHAPES = {
    rest: {},
    A: { jawOpen: 0.9, mouthWide: 0.15 },
    E: { jawOpen: 0.45, mouthWide: 0.7 },
    I: { jawOpen: 0.22, mouthWide: 1 },
    O: { jawOpen: 0.6, mouthPucker: 0.75 },
    U: { jawOpen: 0.25, mouthPucker: 1 },
    MBP: { mouthClose: 1 },
    FV: { jawOpen: 0.12, mouthClose: 0.45, mouthWide: 0.25 },
    S: { jawOpen: 0.15, mouthWide: 0.5 },
  };
  const KEYS = ["jawOpen", "mouthWide", "mouthPucker", "mouthClose"];
  const LETTERS = {
    a: "A", "à": "A", e: "E", "è": "E", "é": "E", i: "I", "ì": "I", y: "I", o: "O", "ò": "O", u: "U", "ù": "U",
    m: "MBP", b: "MBP", p: "MBP", f: "FV", v: "FV", s: "S", z: "S", c: "S", g: "S", x: "S",
    " ": "rest", ",": "MBP", ".": "MBP", "!": "MBP", "?": "MBP", ";": "MBP", ":": "MBP",
  };
  const RATE = 13;
  const SYNTH = ["A", "E", "O", "A", "I", "U"];

  class Visemes {
    constructor() {
      this.w = Object.fromEntries(KEYS.map((k) => [k, 0]));
      this.bands = null; this.bandsAt = 0;
      this.text = ""; this.textAt = 0;
      this.open = 0; this.current = "rest";
    }
    setBands(b) { this.bands = b; this.bandsAt = performance.now(); }
    say(text) { this.text = String(text || "").toLowerCase(); this.textAt = performance.now(); }

    _fromAudio() {
      const { low = 0, mid = 0, high = 0 } = this.bands, tot = low + mid + high + 1e-6;
      if (this.open < 0.08) return "MBP";
      if (high / tot > 0.38) return this.open < 0.35 ? "FV" : "S";
      const ratio = mid / (low + 1e-6);
      if (ratio > 1.15) return this.open > 0.6 ? "E" : "I";
      if (ratio < 0.55) return this.open > 0.6 ? "O" : "U";
      return "A";
    }

    _fromText() {
      const i = Math.floor(((performance.now() - this.textAt) / 1000) * RATE);
      if (!this.text || i >= this.text.length) return null;
      return LETTERS[this.text[i]] || "I";
    }

    update(t, dt, speaking, avatar, morph) {
      const real = avatar.realAudio;
      const level = !speaking ? 0 : real ? avatar.jawTarget
        : avatar.jawTarget * (0.55 + 0.45 * Math.abs(Math.sin(t * 17) * Math.sin(t * 6.3)));
      const boost = avatar.animator.playing("canta") ? 1.3 : 1;
      this.open = damp(this.open, Math.min(1.2, level * boost), real ? 28 : 18, dt);
      let v = "rest";
      if (speaking) {
        if (real && this.bands && performance.now() - this.bandsAt < 250) v = this._fromAudio();
        else v = (!real && this._fromText()) || (this.open < 0.12 ? "MBP" : SYNTH[Math.floor(t * 6) % SYNTH.length]);
      }
      this.current = v;
      const s = SHAPES[v], gain = Math.min(1, this.open * 1.15);
      for (const k of KEYS) {
        const goal = (s[k] || 0) * (k === "mouthClose" ? 1 : gain);
        this.w[k] = damp(this.w[k], goal, 22, dt);
        morph[k] = (morph[k] || 0) + this.w[k];
      }
    }
  }

  H.Visemes = Visemes;
  H.VISEMES = SHAPES;
})(window.Jarvis3D);
