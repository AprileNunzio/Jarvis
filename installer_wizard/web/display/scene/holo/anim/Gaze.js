(function (J) {
  "use strict";
  const { damp } = J;
  const H = (J.Holo = J.Holo || {});

  class Gaze {
    constructor() {
      this.x = 0; this.y = 0; this.tx = 0; this.ty = 0;
      this.target = null; this.targetAt = 0; this.next = 0;
      this.following = false; this.wasThinking = false;
    }

    set(x, y) { this.target = { x, y }; this.targetAt = Date.now(); }

    update(t, dt, thinking) {
      this.following = !!this.target && Date.now() - this.targetAt < 2500;
      if (thinking !== this.wasThinking) { this.wasThinking = thinking; this.next = 0; }
      if (this.following) {
        this.tx = (this.target.x - 0.5) * 0.8;
        this.ty = (0.5 - this.target.y) * 0.45;
        this.next = t + 0.8;
      } else if (t > this.next) {
        if (thinking) { this.tx = -0.24 + (Math.random() - 0.5) * 0.08; this.ty = 0.13 + Math.random() * 0.04; }
        else { this.tx = (Math.random() - 0.5) * 0.35; this.ty = (Math.random() - 0.5) * 0.12; }
        this.next = t + (thinking ? 2.5 : 1.5) + Math.random() * 3.5;
      }
      this.x = damp(this.x, this.tx, 4, dt);
      this.y = damp(this.y, this.ty, 4, dt);
    }
  }

  H.Gaze = Gaze;
})(window.Jarvis3D);
