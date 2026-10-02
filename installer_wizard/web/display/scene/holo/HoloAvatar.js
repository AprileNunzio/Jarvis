(function (J) {
  "use strict";
  const { THREE, damp } = J;
  const H = J.Holo;

  class HoloAvatar {
    constructor(parent, onReady, options = {}) {
      this.group = new THREE.Group();
      this.frame = new THREE.Group();
      this.body = new THREE.Group();
      this.headBone = new THREE.Group();
      this.headBone.matrixAutoUpdate = false;
      this.body.add(this.headBone);
      this.frame.add(this.body);
      this.group.add(this.frame);
      parent.add(this.group);
      this.uniforms = { uTime: { value: 0 }, uOpacity: { value: 0 }, uColor: { value: new THREE.Color(options.color || "#29e0ff") } };
      this.opacity = 1;
      this.jawTarget = 0;
      this.realAudio = false; this.listening = false; this.thinking = false;
      this.groove = 0; this.grooveTarget = 0; this.joy = 0; this.calm = 0; this.calmTarget = 0;
      this.pose = H.blankPose();
      this.gaze = new H.Gaze();
      this.visemes = new H.Visemes();
      this.animator = new H.Animator((name, arg) => this.toggleAccessory(name, arg));
      this.director = new H.Director(this);
      this.parts = [];
      this.accessories = {};
      this._load(options, onReady);
    }

    _load(options, onReady) {
      const done = (gltf) => {
        try { this._build(gltf, options); } catch (err) { console.warn("Ologramma: modello non valido", err); this._build(null, options); }
        onReady && onReady();
      };
      if (!THREE.GLTFLoader) { done(null); return; }
      new THREE.GLTFLoader().load(options.model || "/vendor/head.glb", done, undefined, () => done(null));
    }

    _staticGeometry(gltf) {
      let mesh = null;
      if (gltf) gltf.scene.traverse((o) => { if (o.isMesh && !mesh) mesh = o; });
      if (!mesh) {
        const g = new THREE.SphereGeometry(1, 96, 72), p = g.attributes.position;
        for (let i = 0; i < p.count; i++) p.setXYZ(i, p.getX(i) * 0.78, p.getY(i) * 1.05, p.getZ(i) * 0.9);
        g.computeVertexNormals();
        return g;
      }
      gltf.scene.updateMatrixWorld(true);
      const g = mesh.geometry.clone();
      g.applyMatrix4(mesh.matrixWorld);
      for (const k of Object.keys(g.attributes)) if (!["position", "normal", "uv"].includes(k)) g.deleteAttribute(k);
      g.morphAttributes = {};
      return g;
    }

    _build(gltf, options) {
      let skinned = false;
      if (gltf) gltf.scene.traverse((o) => { if (o.isSkinnedMesh || (o.isMesh && o.morphTargetInfluences)) skinned = true; });
      const yaw = ((+options.yaw || 0) * Math.PI) / 180;
      if (skinned) {
        const root = gltf.scene, box = new THREE.Box3().setFromObject(root), size = new THREE.Vector3(), center = new THREE.Vector3();
        box.getSize(size); box.getCenter(center);
        const s = 2 / Math.max(size.y, 1e-3);
        root.scale.multiplyScalar(s);
        root.position.sub(center).multiplyScalar(s);
        root.rotation.y += yaw;
        this.body.add(root);
        this.rig = new H.NativeRig(root, this.body, this.uniforms, gltf.animations);
        this.L = this.rig.L;
      } else {
        const g = H.Landmarks.normalize(this._staticGeometry(gltf), yaw);
        this.L = H.Landmarks.detect(g);
        this.rig = new H.MeshRig(g, this.L);
        this.parts.push(new H.Face(this, g), new H.Eyes(this));
      }
      if (skinned) this.parts.push(new H.Face(this, null));
      this.framing = new H.Framing(this.frame, this.L);
      for (const name in H.Accessories) this.accessories[name] = H.Accessories[name](this);
      this.parts.push(...Object.values(this.accessories));
    }

    play(name) {
      if (this.rig && this.rig.playClip(name)) return true;
      return this.animator.play(name);
    }
    stop(name) { this.animator.stop(name); }
    express(name, seconds = 2.5) { return this.animator.express(name, seconds) || this.play(name); }
    shot(name, seconds) { return !!this.framing && this.framing.set(name, seconds); }
    setContext(mode) { if (this.framing) this.framing.setContext(mode); }
    direct(text) { this.director.react(text); }
    setVoice(bands) { this.visemes.setBands(bands); }
    setGaze(x, y) { this.gaze.set(x, y); }
    setGroove(v) { this.grooveTarget = Math.max(this.grooveTarget, Math.min(1, v || 0)); }
    setCalm(on) { this.calmTarget = on ? 1 : 0; }
    burst() { this.joy = 1; }
    sing(on) { if (on) this.play("canta"); else this.stop("canta"); }
    dance(on) { if (on) this.play("balla"); else this.stop("balla"); }
    setColor(hex) { this.targetColor = new THREE.Color(hex); }
    toggleAccessory(name, state) { const a = this.accessories[name]; if (a) a.toggle(state); }
    catalog() { return { ...H.Library.catalog(), accessori: Object.keys(this.accessories), inquadrature: ["intera", "mezzo", "primo_piano"] }; }

    update(t, dt, speaking) {
      const u = this.uniforms;
      u.uTime.value = t;
      u.uOpacity.value = damp(u.uOpacity.value, this.opacity, 3, dt);
      if (this.targetColor) u.uColor.value.lerp(this.targetColor, 1 - Math.exp(-3 * dt));
      this.grooveTarget = damp(this.grooveTarget, 0, 2.5, dt);
      this.groove = damp(this.groove, this.grooveTarget, 12, dt);
      this.joy = damp(this.joy, 0, 1.6, dt);
      this.calm = damp(this.calm, this.calmTarget, 0.8, dt);
      this.group.visible = u.uOpacity.value > 0.01;
      if (!this.rig || !this.group.visible) return;
      const st = { speaking, listening: this.listening, thinking: this.thinking, groove: this.groove,
                   joy: this.joy, calm: this.calm, jaw: this.visemes.open };
      this.gaze.update(t, dt, this.thinking);
      this.animator.update(t, dt, st, this.pose, this.gaze);
      this.visemes.update(t, dt, speaking, this, this.pose.morph);
      this.animator.finish(this.pose, this.calm);
      this.rig.opacity = u.uOpacity.value;
      this.rig.apply(this.pose, dt);
      this.headBone.matrix.copy(this.rig.headMatrix);
      this.headBone.matrixWorldNeedsUpdate = true;
      this.body.scale.setScalar(this.pose.breath);
      this.framing.update(dt, speaking);
      for (const p of this.parts) p.update(t, dt, this.pose);
    }
  }

  J.HoloFace = HoloAvatar;
  H.HoloAvatar = HoloAvatar;
})(window.Jarvis3D);
