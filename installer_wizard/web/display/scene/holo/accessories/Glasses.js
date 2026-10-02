(function (J) {
  "use strict";
  const { THREE } = J;
  const H = J.Holo;

  function lens(rx, ry) {
    const v = [];
    for (let i = 0; i <= 40; i++) { const a = (i / 40) * Math.PI * 2; v.push(Math.cos(a) * rx, Math.sin(a) * ry, 0); }
    return new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(v, 3));
  }

  H.Accessories.glasses = (avatar) => new H.Accessory(avatar, 1, (mat, line, L) => {
    const F = L.F, e = L.eye, g = new THREE.Group(), geo = lens(F * 0.55, F * 0.38);
    const left = new THREE.Line(geo, line), right = new THREE.Line(geo, line);
    left.position.x = -e.x; right.position.x = e.x;
    const gap = e.x - F * 0.55;
    const bridge = new THREE.Line(new THREE.BufferGeometry().setAttribute("position",
      new THREE.Float32BufferAttribute([-gap, F * 0.08, 0, 0, F * 0.14, 0, gap, F * 0.08, 0], 3)), line);
    const arms = [-1, 1].map((sx) => new THREE.Line(new THREE.BufferGeometry().setAttribute("position",
      new THREE.Float32BufferAttribute([sx * (e.x + F * 0.55), 0, 0, sx * L.earX * 0.95, F * 0.05, L.centerZ - (e.z + F * 0.3)], 3)), line));
    g.add(left, right, bridge, ...arms);
    g.position.set(0, e.y, e.z + F * 0.3);
    return g;
  });
})(window.Jarvis3D);
