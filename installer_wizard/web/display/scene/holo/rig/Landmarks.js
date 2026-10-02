(function (J) {
  "use strict";
  const { THREE } = J;
  const H = (J.Holo = J.Holo || {});

  function normalize(g, yaw) {
    if (yaw) g.rotateY(yaw);
    g.computeBoundingBox();
    const size = new THREE.Vector3(), center = new THREE.Vector3();
    g.boundingBox.getSize(size); g.boundingBox.getCenter(center);
    const s = 2 / Math.max(size.y, 1e-3);
    g.translate(-center.x, -center.y, -center.z);
    g.scale(s, s, s);
    if (!g.attributes.normal) g.computeVertexNormals();
    g.computeBoundingBox();
    return g;
  }

  function sampler(P) {
    const n = P.length;
    return {
      zMax(y, x, dy, dx) {
        let z = -Infinity;
        for (let i = 0; i < n; i += 3) if (Math.abs(P[i + 1] - y) < dy && Math.abs(P[i] - x) < dx && P[i + 2] > z) z = P[i + 2];
        return z;
      },
      zMin(y, dy) {
        let z = Infinity;
        for (let i = 0; i < n; i += 3) if (Math.abs(P[i + 1] - y) < dy && P[i + 2] < z) z = P[i + 2];
        return z;
      },
      half(y, dy) {
        let w = 0;
        for (let i = 0; i < n; i += 3) if (Math.abs(P[i + 1] - y) < dy) w = Math.max(w, Math.abs(P[i]));
        return w;
      },
    };
  }

  function detect(g) {
    const P = g.attributes.position.array, box = g.boundingBox, S = sampler(P);
    const top = box.max.y, bottom = box.min.y, height = top - bottom, dy = height * 0.012;
    const nose = new THREE.Vector3(0, 0, -Infinity);
    for (let i = 0; i < P.length; i += 3) {
      if (P[i + 1] > bottom + height * 0.3 && Math.abs(P[i]) < height * 0.05 && P[i + 2] > nose.z) nose.set(P[i], P[i + 1], P[i + 2]);
    }
    const span = Math.max(top - nose.y, height * 0.1), F = span * 0.24;
    const side = (y) => (S.zMax(y, -F, dy, span * 0.05) + S.zMax(y, F, dy, span * 0.05)) / 2;
    let eyeY = nose.y + span * 0.15, eyeZ = Infinity;
    for (let y = nose.y + span * 0.05; y < nose.y + span * 0.4; y += dy) {
      const z = side(y);
      if (isFinite(z) && z < eyeZ) { eyeZ = z; eyeY = y; }
    }
    if (!isFinite(eyeZ)) eyeZ = nose.z - span * 0.25;
    const depth = Math.max(nose.z - eyeZ, span * 0.08);
    const mid = (y) => S.zMax(y, nose.x, dy * 1.5, span * 0.06);
    let chinY = nose.y - span * 0.55;
    for (let y = nose.y - span * 0.3; y > nose.y - span * 1.2; y -= dy) if (mid(y) < nose.z - depth * 0.8) { chinY = y; break; }
    const subnasal = nose.y - (nose.y - chinY) * 0.18;
    const mouthY = subnasal - (subnasal - chinY) * 0.25;
    const mz = mid(mouthY), mouthZ = isFinite(mz) ? mz : nose.z - depth * 0.5;
    const back = S.zMin(mouthY, dy * 3), backZ = isFinite(back) ? back : -nose.z;
    const neckHalf = S.half(chinY - F * 0.4, dy * 2) || F;
    let shoulderY = bottom - 1;
    for (let y = chinY - F * 0.4; y > bottom; y -= dy) if (S.half(y, dy) > neckHalf * 1.6) { shoulderY = y; break; }
    return {
      F, top, bottom, nose,
      eye: { x: F * 0.8, y: eyeY + F * 0.4, z: (S.zMax(eyeY + F * 0.4, -F * 0.8, dy, span * 0.05) + S.zMax(eyeY + F * 0.4, F * 0.8, dy, span * 0.05)) / 2 },
      mouth: { y: mouthY, z: mouthZ, w: F * 0.8 },
      chin: { y: chinY },
      jaw: new THREE.Vector3(0, nose.y - F * 0.1, backZ + (mouthZ - backZ) * 0.45),
      neck: new THREE.Vector3(0, chinY - F * 0.2, backZ + (mouthZ - backZ) * 0.4),
      shoulderY, centerZ: backZ + (mouthZ - backZ) * 0.5,
      earX: S.half(eyeY - F * 0.3, dy * 2) || F * 2.4,
      crown: S.half(top - F * 0.6, dy * 2) || F * 2,
    };
  }

  function fromHead(box, headPos) {
    const top = box.max.y, size = Math.max(top - headPos.y, 0.05) * 1.6, F = size * 0.16;
    const eyeY = headPos.y + size * 0.35, front = headPos.z + size * 0.45;
    return {
      F, top, bottom: box.min.y, nose: new THREE.Vector3(0, eyeY - F, front + F * 0.4),
      eye: { x: F, y: eyeY, z: front }, mouth: { y: eyeY - F * 2, z: front, w: F * 0.8 },
      chin: { y: headPos.y - size * 0.15 }, jaw: headPos.clone(), neck: headPos.clone(),
      shoulderY: headPos.y - size * 0.6, centerZ: headPos.z, earX: size * 0.42, crown: size * 0.4,
    };
  }

  H.Landmarks = { normalize, detect, fromHead };
})(window.Jarvis3D);
