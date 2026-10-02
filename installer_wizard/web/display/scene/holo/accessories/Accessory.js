(function (J) {
  "use strict";
  const { THREE, damp } = J;
  const H = (J.Holo = J.Holo || {});

  class Accessory {
    constructor(avatar, peak, build) {
      this.a = avatar;
      this.peak = peak;
      this.active = false;
      this.opacity = 0;
      this.mat = new THREE.MeshBasicMaterial({ color: avatar.uniforms.uColor.value.clone(), wireframe: true,
        transparent: true, opacity: 0, depthWrite: false });
      this.line = new THREE.LineBasicMaterial({ color: avatar.uniforms.uColor.value.clone(), transparent: true, opacity: 0 });
      this.mesh = build(this.mat, this.line, avatar.L);
      this.mesh.visible = false;
      avatar.headBone.add(this.mesh);
    }

    toggle(state) { this.active = state === undefined ? !this.active : !!state; }

    update(t, dt) {
      this.opacity = damp(this.opacity, this.active ? this.peak : 0, 4, dt);
      this.mesh.visible = this.opacity > 0.01;
      if (!this.mesh.visible) return;
      const u = this.a.uniforms;
      for (const m of [this.mat, this.line]) { m.opacity = this.opacity * u.uOpacity.value; m.color.copy(u.uColor.value); }
    }
  }

  H.Accessory = Accessory;
  H.Accessories = {};
})(window.Jarvis3D);
