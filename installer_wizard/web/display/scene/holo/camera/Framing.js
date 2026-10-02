(function (J) {
  "use strict";
  const { damp } = J;
  const H = (J.Holo = J.Holo || {});
  const VIEW = 1.9;
  const NAMES = { intera: "intera", full: "intera", figura_intera: "intera", mezzo: "mezzo", busto: "mezzo",
                  mezzo_busto: "mezzo", primo_piano: "primo_piano", close: "primo_piano", volto: "primo_piano" };

  class Framing {
    constructor(frame, L) {
      this.frame = frame;
      const low = Math.max(L.bottom, L.chin.y - L.F * 0.9), high = L.top + L.F * 0.15;
      const k = Math.max(1, VIEW / Math.max(0.2, high - low)), y = -((high + low) / 2) * k;
      this.shots = { intera: { k: 1, y: 0 }, mezzo: { k: (1 + k) / 2, y: y / 2 }, primo_piano: { k, y } };
      this.kClose = k;
      this.auto = "intera"; this.forced = null; this.until = 0; this.context = null;
      this.k = 1; this.y = 0; this.closeness = 0; this.lastSpeech = 0;
    }

    static resolve(name) { return NAMES[String(name || "").toLowerCase().replace(/\s+/g, "_")] || null; }

    set(name, seconds = 12) {
      const shot = Framing.resolve(name);
      if (!shot) return false;
      this.forced = shot;
      this.until = Date.now() + seconds * 1000;
      return true;
    }

    suggest(name) { const shot = Framing.resolve(name); if (shot) this.auto = shot; }
    setContext(mode) { this.context = mode === "focus" ? "primo_piano" : null; }

    current() {
      if (this.forced && Date.now() < this.until) return this.forced;
      return this.context || this.auto;
    }

    update(dt, speaking) {
      const now = Date.now();
      if (speaking) this.lastSpeech = now;
      else if (this.auto !== "intera" && now - this.lastSpeech > 6000) this.auto = "intera";
      const s = this.shots[this.current()];
      this.k = damp(this.k, s.k, 2.2, dt);
      this.y = damp(this.y, s.y, 2.2, dt);
      this.frame.scale.setScalar(this.k);
      this.frame.position.y = this.y;
      this.closeness = this.kClose > 1 ? Math.min(1, (this.k - 1) / (this.kClose - 1)) : 0;
    }
  }

  H.Framing = Framing;
})(window.Jarvis3D);
