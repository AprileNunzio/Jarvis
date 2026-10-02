(function (J) {
  "use strict";
  const { THREE } = J;
  const H = J.Holo;

  H.Accessories.hat = (avatar) => new H.Accessory(avatar, 0.8, (mat, line, L) => {
    const r = L.crown * 1.15, g = new THREE.Group();
    const brim = new THREE.Mesh(new THREE.CylinderGeometry(r * 1.45, r * 1.45, L.F * 0.08, 40), mat);
    const crown = new THREE.Mesh(new THREE.CylinderGeometry(r * 0.92, r, L.F * 1.6, 32), mat);
    crown.position.y = L.F * 0.8;
    g.add(brim, crown);
    g.position.set(0, L.top - L.F * 0.95, L.centerZ);
    g.rotation.x = -0.08;
    return g;
  });
})(window.Jarvis3D);
