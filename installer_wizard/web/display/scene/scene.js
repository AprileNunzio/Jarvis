(function (global, J) {
  "use strict";
  const { THREE, damp, HoloFace, HoloBrain } = J;

  class JarvisScene {
    constructor(canvas, handlers = {}) {
      this.handlers = handlers;
      this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
      this.renderer.setPixelRatio(Math.min(2, global.devicePixelRatio || 1));
      this.scene = new THREE.Scene();
      this.camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
      this.camera.position.set(0, 0, 6.2);
      this.controls = new THREE.OrbitControls(this.camera, canvas);
      this.controls.enableDamping = true;
      this.controls.enablePan = false;
      this.controls.minDistance = 2.2;
      this.controls.maxDistance = 9;
      this.controls.enabled = false;
      this.controls.addEventListener("start", () => (this.brain.autoRotate = false));
      this.frames = 0;
      if (handlers.face === false) {
        this.face = null;
      } else {
        this.face = new HoloFace(this.scene, () => handlers.onFaceReady && handlers.onFaceReady(),
                                 handlers.faceOptions || {});
      }
      this.brain = new HoloBrain(this.scene);
      this.mode = "face";
      this.speaking = false;
      this.clock = new THREE.Clock();
      this.faceTarget = { x: 0, y: 0.05, s: 1 };
      this.raycaster = new THREE.Raycaster();
      this.raycaster.params.Points.threshold = 0.06;
      this.pointer = new THREE.Vector2();
      canvas.addEventListener("pointerdown", (e) => (this._down = [e.clientX, e.clientY]));
      canvas.addEventListener("pointerup", (e) => this._click(e));
      canvas.addEventListener("pointermove", (e) => this._hover(e));
      global.addEventListener("resize", () => this.resize());
      this.resize();
      this.renderer.setAnimationLoop(() => this._frame());
    }
    resize() {
      const w = global.innerWidth, h = global.innerHeight;
      this.renderer.setSize(w, h, false);
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
      this.setMode(this.mode, true);
    }
    setMode(mode, silent) {
      const prev = this.mode;
      this.mode = mode;
      const dist = 6.2, vh = 2 * Math.tan((this.camera.fov * Math.PI) / 360) * dist, vw = vh * this.camera.aspect;
      const narrow = this.camera.aspect < 1;
      if (mode === "focus") {
        this.faceTarget = narrow ? { x: 0, y: vh * 0.34, s: 0.32 } : { x: -vw * 0.38, y: vh * 0.24, s: 0.42 };
      } else if (this.stage) {
        const z = this.stage, W = global.innerWidth, H = global.innerHeight;
        this.faceTarget = { x: (z.cx / W - 0.5) * vw, y: (0.5 - z.cy / H) * vh + 0.05,
                            s: Math.max(0.28, Math.min(1, Math.min(z.w / W, z.h / H) * 1.15)) };
      } else {
        this.faceTarget = { x: 0, y: 0.05, s: 1 };
      }
      if (mode !== "brain") this.faceTarget.s *= this.presence || 1;
      if (this.face) { this.face.opacity = mode === "brain" ? 0 : 1; if (this.face.setContext) this.face.setContext(mode); }
      else if (mode === "brain" && this._sleeping) { this._sleeping = false; this.clock.getDelta(); this.renderer.setAnimationLoop(() => this._frame()); }
      this.brain.opacity = mode === "brain" ? 1 : 0;
      this.controls.enabled = mode === "brain";
      this.brain.autoRotate = mode === "brain";
      if (mode !== "brain" && prev === "brain" && !silent) this._resetCamera = true;
      if (mode === "brain" && prev !== "brain") {
        this.camera.position.set(0, 0.5, 5.4);
        this.controls.target.set(0, -0.05, 0);
        this.brain.group.rotation.y = Math.PI / 2;
      }
      this.brain.group.position.x = narrow ? 0 : 0.35;
    }
    setStage(zone) { this.stage = zone; if (this.mode === "face") this.setMode("face", true); }
    setPresence(k) { this.presence = k; this.setMode(this.mode, true); }
    setSpeaking(on, level = 1) { this.speaking = on; if (this.face) this.face.jawTarget = on ? level : 0; }
    setTint(hex) { if (this.face) this.face.setColor(hex); }
    setGroove(v) { if (this.face && this.face.setGroove) this.face.setGroove(v); }
    setGaze(x, y) { if (this.face && this.face.setGaze) this.face.setGaze(x, y); }
    express(name, seconds) { if (this.face && this.face.express) this.face.express(name, seconds); }
    setCalm(on) { if (this.face && this.face.setCalm) this.face.setCalm(on); }
    burst() { if (this.face && this.face.burst) this.face.burst(); }
    play(name) { return !!(this.face && this.face.play && this.face.play(name)); }
    stop(name) { if (this.face && this.face.stop) this.face.stop(name); }
    shot(name, seconds) { return !!(this.face && this.face.shot && this.face.shot(name, seconds)); }
    sing(on) { if (this.face && this.face.sing) this.face.sing(on); }
    dance(on) { if (this.face && this.face.dance) this.face.dance(on); }
    toggleAccessory(name, state) { if (this.face && this.face.toggleAccessory) this.face.toggleAccessory(name, state); }
    setVoice(bands) { if (this.face && this.face.setVoice) this.face.setVoice(bands); }
    direct(text) { if (this.face && this.face.direct) this.face.direct(text); }
    _pick(e) {
      if (this.mode !== "brain" || !this.brain.neurons) return null;
      const r = this.renderer.domElement.getBoundingClientRect();
      this.pointer.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      this.raycaster.setFromCamera(this.pointer, this.camera);
      const hit = this.raycaster.intersectObject(this.brain.neurons)[0];
      return hit ? this.brain.nodeAt(hit.index) : null;
    }
    _click(e) {
      if (!this._down || Math.hypot(e.clientX - this._down[0], e.clientY - this._down[1]) > 6) return;
      const hit = this._pick(e);
      if (hit) { this.brain.select(hit.node.id); this.focusOn(hit.pos); }
      this.handlers.onSelect && this.handlers.onSelect(hit ? hit.node : null);
    }
    _hover(e) {
      const hit = this._pick(e);
      this.renderer.domElement.style.cursor = hit ? "pointer" : (this.mode === "brain" ? "grab" : "default");
      this.handlers.onHover && this.handlers.onHover(hit ? hit.node : null, e);
    }
    focusOn(pos) { this._flyTarget = pos.clone().applyMatrix4(this.brain.group.matrixWorld); }
    _frame() {
      const dt = Math.min(0.05, this.clock.getDelta()), t = this.clock.elapsedTime;
      this.frames++;
      if (this.face) {
        const g = this.face.group;
        g.position.x = damp(g.position.x, this.faceTarget.x, 3.5, dt);
        g.position.y = damp(g.position.y, this.faceTarget.y, 3.5, dt);
        g.scale.setScalar(damp(g.scale.x, this.faceTarget.s, 3.5, dt));
      }
      if (this._resetCamera) {
        this.camera.position.lerp(new THREE.Vector3(0, 0, 6.2), 1 - Math.exp(-4 * dt));
        this.controls.target.lerp(new THREE.Vector3(0, 0, 0), 1 - Math.exp(-4 * dt));
        if (this.camera.position.distanceTo(new THREE.Vector3(0, 0, 6.2)) < 0.01) this._resetCamera = false;
      }
      if (this._flyTarget) {
        this.controls.target.lerp(this._flyTarget, 1 - Math.exp(-3 * dt));
        if (this.controls.target.distanceTo(this._flyTarget) < 0.005) this._flyTarget = null;
      }
      if (this.face) this.face.update(t, dt, this.speaking);
      this.brain.update(t, dt);
      if (!this.face && this.mode !== "brain" && this.brain.uniforms.uOpacity.value < 0.01) {
        this.renderer.clear();
        this.renderer.setAnimationLoop(null);
        this._sleeping = true;
        return;
      }
      if (this.controls.enabled) this.controls.update(); else this.camera.lookAt(this.controls.target);
      this.renderer.render(this.scene, this.camera);
    }
  }

  Object.assign(J, { JarvisScene });
})(window, window.Jarvis3D);
