(function (J) {
  "use strict";
  const { THREE } = J;
  const H = (J.Holo = J.Holo || {});

  const WIRE_VERT = `
    uniform float uTime;
    varying float vFront, vY;
    void main() {
      vec3 p = position + normal * sin(uTime * 2.0 + position.y * 30.0) * 0.003;
      vec4 mv = modelViewMatrix * vec4(p, 1.0);
      vec3 n = normalize(normalMatrix * normal);
      vFront = clamp(dot(n, normalize(-mv.xyz)), 0.0, 1.0);
      vY = p.y;
      gl_Position = projectionMatrix * mv;
    }`;
  const WIRE_FRAG = `
    uniform vec3 uColor; uniform float uTime, uOpacity;
    varying float vFront, vY;
    void main() {
      float scan = smoothstep(0.04, 0.0, abs(fract(vY * 0.45 - uTime * 0.14) - 0.5) - 0.46);
      float b = 0.22 + vFront * 0.75 + scan * 0.3;
      gl_FragColor = vec4(mix(uColor, vec3(1.0), vFront * 0.25 + scan * 0.25), clamp(b, 0.0, 1.0) * uOpacity);
    }`;
  const SHELL_VERT = `
    varying float vRim;
    void main() {
      vec4 mv = modelViewMatrix * vec4(position, 1.0);
      vec3 n = normalize(normalMatrix * normal);
      vRim = pow(1.0 - abs(dot(n, normalize(-mv.xyz))), 2.2);
      gl_Position = projectionMatrix * mv;
    }`;
  const SHELL_FRAG = `
    uniform vec3 uColor; uniform float uOpacity; varying float vRim;
    void main() {
      vec3 base = vec3(0.012, 0.05, 0.09);
      gl_FragColor = vec4(mix(base, uColor, vRim * 0.6), (0.82 + vRim * 0.18) * uOpacity);
    }`;

  class Face {
    constructor(avatar, geometry) {
      this.a = avatar;
      if (geometry) {
        const shell = new THREE.Mesh(geometry, new THREE.ShaderMaterial({ uniforms: avatar.uniforms,
          vertexShader: SHELL_VERT, fragmentShader: SHELL_FRAG, transparent: true, depthWrite: true }));
        shell.scale.setScalar(0.985);
        const wire = new THREE.Mesh(geometry, new THREE.ShaderMaterial({ uniforms: avatar.uniforms,
          vertexShader: WIRE_VERT, fragmentShader: WIRE_FRAG, transparent: true, depthWrite: false, wireframe: true,
          polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 }));
        shell.renderOrder = 0; wire.renderOrder = 1;
        shell.frustumCulled = wire.frustumCulled = false;
        avatar.body.add(shell, wire);
      }
      const L = avatar.L, floor = L.bottom - 0.12;
      const mat = new THREE.MeshBasicMaterial({ color: "#29e0ff", transparent: true, opacity: 0.25,
        blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
      this.rings = [0.9, 1.15, 1.4].map((r, i) => {
        const ring = new THREE.Mesh(new THREE.RingGeometry(r, r + 0.012 + i * 0.004, 128), mat.clone());
        ring.rotation.x = -Math.PI / 2;
        ring.position.y = floor;
        avatar.frame.add(ring);
        return ring;
      });
    }

    update(t) {
      const a = this.a, g = a.groove, mo = 1 - a.calm * 0.6, u = a.uniforms;
      const fade = (1 - a.framing.closeness) * (1 - a.calm * 0.4) * u.uOpacity.value;
      this.rings.forEach((r, i) => {
        r.rotation.z = t * (0.2 + i * 0.1) * (i % 2 ? -1 : 1) * (1 + g * 2.5) * mo;
        r.material.opacity = (0.12 + 0.12 * Math.sin(t * 1.5 + i) + g * 0.2 + a.joy * 0.3) * fade;
        r.material.color.copy(u.uColor.value);
        r.visible = r.material.opacity > 0.005;
      });
    }
  }

  H.Face = Face;
})(window.Jarvis3D);
