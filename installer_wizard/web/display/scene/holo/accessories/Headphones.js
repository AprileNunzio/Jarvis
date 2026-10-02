(function (J) {
  "use strict";
  const { THREE } = J;
  const H = J.Holo;

  H.Accessories.headphones = (avatar) => new H.Accessory(avatar, 0.7, (mat, line, L) => {
    const F = L.F, x = L.earX * 1.04, y = L.eye.y - F * 0.35, g = new THREE.Group();
    [-1, 1].forEach((sx) => {
      const cup = new THREE.Mesh(new THREE.CylinderGeometry(F * 0.55, F * 0.55, F * 0.35, 18), mat);
      cup.rotation.z = Math.PI / 2;
      cup.position.set(sx * x, 0, 0);
      g.add(cup);
    });
    const band = new THREE.Mesh(new THREE.TorusGeometry(x, F * 0.07, 8, 40, Math.PI), mat);
    band.scale.y = Math.max(1, (L.top + F * 0.1 - y) / x);
    g.add(band);
    g.position.set(0, y, L.centerZ);
    return g;
  });
})(window.Jarvis3D);
