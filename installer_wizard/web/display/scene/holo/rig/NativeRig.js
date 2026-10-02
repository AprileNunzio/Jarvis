(function (J) {
  "use strict";
  const { THREE } = J;
  const H = (J.Holo = J.Holo || {});
  const MORPHS = {
    jawOpen: ["jawOpen", "mouthOpen", "viseme_aa"],
    mouthWide: ["mouthStretchLeft", "mouthStretchRight", "viseme_E", "viseme_I"],
    mouthPucker: ["mouthPucker", "mouthFunnel", "viseme_O", "viseme_U"],
    mouthClose: ["mouthClose", "viseme_PP"],
    mouthSmile: ["mouthSmile", "mouthSmileLeft", "mouthSmileRight", "smile"],
    mouthFrown: ["mouthFrown", "mouthFrownLeft", "mouthFrownRight", "sad"],
    browUp: ["browOuterUpLeft", "browOuterUpRight", "surprise"],
    browInner: ["browInnerUp"],
    browDown: ["browDownLeft", "browDownRight"],
    eyeBlink: ["eyeBlinkLeft", "eyeBlinkRight", "eyesClosed", "blink"],
    eyeSquint: ["eyeSquintLeft", "eyeSquintRight", "cheekSquintLeft", "cheekSquintRight"],
    eyeWide: ["eyeWideLeft", "eyeWideRight"],
  };
  const SHARE = { neck: 0.35, head: 0.65 };

  class NativeRig {
    constructor(root, body, uniforms, clips) {
      this.root = root;
      this.body = body;
      this.meshes = [];
      this.bones = {};
      root.traverse((o) => {
        if (o.isMesh) {
          o.material = new THREE.MeshBasicMaterial({ color: uniforms.uColor.value, wireframe: true, transparent: true,
            skinning: !!o.isSkinnedMesh, morphTargets: !!o.morphTargetInfluences });
          o.frustumCulled = false;
          this.meshes.push(o);
        }
        if (o.isBone) {
          const n = o.name.toLowerCase();
          if (!this.bones.head && /head/.test(n) && !/end|top|nub|_end/.test(n)) this.bones.head = o;
          if (!this.bones.neck && /neck/.test(n)) this.bones.neck = o;
        }
      });
      this.rest = {};
      for (const k in this.bones) this.rest[k] = this.bones[k].quaternion.clone();
      this.rootRest = root.quaternion.clone();
      this.targets = this.meshes.filter((m) => m.morphTargetDictionary).map((m) => ({ m, map: this._resolve(m.morphTargetDictionary) }));
      this.mixer = clips && clips.length ? new THREE.AnimationMixer(root) : null;
      this.clips = {};
      (clips || []).forEach((c) => (this.clips[c.name.toLowerCase()] = c));
      this.headMatrix = new THREE.Matrix4();
      this._restRel = new THREE.Matrix4();
      this._inv = new THREE.Matrix4();
      this._e = new THREE.Euler();
      this._q = new THREE.Quaternion();
      this._relative(this._restRel);
      this._restRel.invert();
      this.L = this._landmarks();
    }

    _resolve(dict) {
      const map = {};
      for (const k in MORPHS) map[k] = MORPHS[k].map((n) => dict[n]).filter((i) => i !== undefined);
      return map;
    }

    _relative(out) {
      const bone = this.bones.head || this.root;
      this.body.updateWorldMatrix(true, true);
      this._inv.copy(this.body.matrixWorld).invert();
      return out.multiplyMatrices(this._inv, bone.matrixWorld);
    }

    _landmarks() {
      const box = new THREE.Box3().setFromObject(this.root);
      this._inv.copy(this.body.matrixWorld).invert();
      box.applyMatrix4(this._inv);
      const head = new THREE.Vector3().setFromMatrixPosition(this._relative(new THREE.Matrix4()));
      if (!this.bones.head) head.set(0, box.max.y - (box.max.y - box.min.y) * 0.12, 0);
      return H.Landmarks.fromHead(box, head);
    }

    playClip(name) {
      if (!this.mixer) return false;
      const key = String(name).toLowerCase();
      const clip = this.clips[key] || Object.values(this.clips).find((c) => c.name.toLowerCase().includes(key));
      if (!clip) return false;
      const action = this.mixer.clipAction(clip);
      action.reset().setLoop(THREE.LoopOnce, 1).fadeIn(0.3).play();
      action.clampWhenFinished = false;
      return true;
    }

    apply(pose, dt) {
      if (this.mixer) this.mixer.update(dt);
      const has = Object.keys(this.bones).length > 0;
      if (has) {
        for (const k in this.bones) {
          const s = SHARE[k] || 0;
          this._e.set(pose.rx * s, pose.ry * s, pose.rz * s);
          this.bones[k].quaternion.copy(this.rest[k]).multiply(this._q.setFromEuler(this._e));
        }
      } else {
        this._e.set(pose.rx, pose.ry, pose.rz);
        this.root.quaternion.copy(this.rootRest).multiply(this._q.setFromEuler(this._e));
      }
      for (const { m, map } of this.targets) {
        const inf = m.morphTargetInfluences;
        for (const k in map) for (const i of map[k]) inf[i] = 0;
        for (const k in map) {
          const w = Math.max(0, Math.min(1, pose.morph[k] || 0));
          for (const i of map[k]) inf[i] = Math.max(inf[i], w);
        }
      }
      this.headMatrix.multiplyMatrices(this._relative(this.headMatrix), this._restRel);
      for (const m of this.meshes) m.material.opacity = this.opacity == null ? 1 : this.opacity;
    }
  }

  H.NativeRig = NativeRig;
})(window.Jarvis3D);
