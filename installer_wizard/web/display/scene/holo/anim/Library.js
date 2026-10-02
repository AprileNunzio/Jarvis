(function (J) {
  "use strict";
  const H = (J.Holo = J.Holo || {});

  const EMOTIONS = {
    neutral: {},
    smile: { mouthSmile: 0.9, eyeSquint: 0.35, browUp: 0.1 },
    sad: { mouthFrown: 0.8, browInner: 0.9, eyeSquint: 0.2, rx: 0.08 },
    cry: { mouthFrown: 1, browInner: 1, eyeSquint: 0.6, jawOpen: 0.15, rx: 0.12 },
    surprise: { browUp: 1, eyeWide: 0.9, jawOpen: 0.35, mouthPucker: 0.2, rx: -0.05 },
    disagree: { browDown: 0.7, mouthFrown: 0.35, ry: 0.35 },
    angry: { browDown: 1, mouthClose: 0.5, mouthWide: 0.2, rx: 0.06 },
    doubt: { browInner: 0.5, mouthFrown: 0.25, rz: 0.08 },
    think: { browDown: 0.25, mouthClose: 0.3, ry: -0.15, rx: -0.08 },
  };

  const MACRO = {
    saluto: { dur: 2.2, tracks: {
      rx: [[0, 0], [0.35, 0.16], [0.8, -0.04], [1.3, 0]],
      rz: [[0, 0], [0.5, 0.1], [1.6, 0.1], [2.2, 0]],
      mouthSmile: [[0, 0], [0.4, 0.9], [1.8, 0.9], [2.2, 0]],
      eyeSquint: [[0, 0], [0.5, 0.35], [1.8, 0.35], [2.2, 0]],
      browUp: [[0, 0], [0.3, 0.6], [0.8, 0], [2.2, 0]] } },
    annuisce: { dur: 1.4, tracks: { rx: [[0, 0], [0.2, 0.14], [0.45, -0.03], [0.7, 0.12], [0.95, -0.02], [1.4, 0]] } },
    disaccordo: { dur: 1.6, tracks: {
      ry: [[0, 0], [0.2, 0.22], [0.5, -0.22], [0.8, 0.18], [1.1, -0.12], [1.6, 0]],
      browDown: [[0, 0], [0.3, 0.6], [1.3, 0.6], [1.6, 0]],
      mouthFrown: [[0, 0], [0.3, 0.4], [1.3, 0.4], [1.6, 0]] } },
    inchino: { dur: 2.2, tracks: {
      rx: [[0, 0], [0.6, 0.38], [1.3, 0.38], [2.2, 0]], py: [[0, 0], [0.6, -0.04], [1.3, -0.04], [2.2, 0]],
      mouthSmile: [[0, 0], [1.4, 0.2], [2.2, 0.5]] } },
    cappello: { dur: 1.8, events: [[0.7, "hat", true]], tracks: {
      rx: [[0, 0], [0.5, 0.25], [0.9, 0.25], [1.3, -0.05], [1.8, 0]],
      mouthSmile: [[0, 0], [1.0, 0], [1.3, 0.7], [1.8, 0]] } },
    togli_cappello: { dur: 1.6, events: [[0.6, "hat", false]], tracks: {
      rx: [[0, 0], [0.4, 0.2], [0.8, 0.2], [1.6, 0]], mouthSmile: [[0, 0], [0.8, 0.5], [1.6, 0]] } },
    ascolto: { loop: true, tracks: { rz: [[0, 0.09]], rx: [[0, 0.05]], browUp: [[0, 0.15]] } },
    pensa: { loop: true, tracks: { ry: [[0, -0.18]], rx: [[0, -0.1]], browDown: [[0, 0.3]], mouthClose: [[0, 0.3]] },
      osc: { rz: [0.02, 0.4, 0] } },
    balla: { loop: true, tracks: { mouthSmile: [[0, 0.5]] },
      osc: { ry: [0.14, 3.1, 0], rz: [0.1, 6.2, 0], px: [0.06, 3.1, 0], py: [0.08, 6.2, 0, 1], breath: [0.03, 12.4, 0] } },
    canta: { loop: true, tracks: { browUp: [[0, 0.4]], eyeSquint: [[0, 0.3]] },
      osc: { rx: [0.03, 8, 0], rz: [0.05, 2.1, 0] } },
  };

  const MICRO = {
    blink: { dur: 0.18, tracks: { eyeBlink: [[0, 0], [0.07, 1], [0.18, 0]] } },
    microsorriso: { dur: 1.6, tracks: { mouthSmile: [[0, 0], [0.4, 0.35], [1.2, 0.35], [1.6, 0]] } },
    sopracciglio: { dur: 0.7, tracks: { browUp: [[0, 0], [0.15, 0.7], [0.45, 0.7], [0.7, 0]] } },
    sussulto: { dur: 0.6, tracks: { eyeWide: [[0, 0], [0.1, 0.8], [0.6, 0]], rx: [[0, 0], [0.1, -0.05], [0.6, 0]] } },
    annuisce_lieve: { dur: 0.7, tracks: { rx: [[0, 0], [0.2, 0.06], [0.45, 0], [0.7, 0]] } },
  };

  const ALIASES = {
    ciao: "saluto", saluta: "saluto", wave: "saluto", greet: "saluto",
    si: "annuisce", "sì": "annuisce", yes: "annuisce", nod: "annuisce", annuisci: "annuisce",
    no: "disaccordo", nega: "disaccordo",
    bow: "inchino", hat: "cappello", "metti_cappello": "cappello", "via_cappello": "togli_cappello",
    listen: "ascolto", ascolta: "ascolto", think: "pensa", pensa: "pensa",
    dance: "balla", danza: "balla", sing: "canta",
    gioia: "smile", felice: "smile", sorriso: "smile", triste: "sad", piange: "cry", sorpresa: "surprise",
    disaccordo_volto: "disagree", arrabbiato: "angry", rabbia: "angry", dubbio: "doubt", pensieroso: "think",
  };

  const HEAD = new Set(["rx", "ry", "rz", "px", "py", "breath"]);

  function key(name) {
    const k = String(name || "").trim().toLowerCase().replace(/\s+/g, "_");
    return ALIASES[k] || k;
  }

  function prepare(set, layer) {
    for (const name in set) {
      const c = set[name];
      c.layer = layer;
      c.fade = c.fade == null ? (layer === "macro" ? 0.25 : 0) : c.fade;
      c.tracks = c.tracks || {};
      if (!c.dur) c.dur = Math.max(0, ...Object.values(c.tracks).map((k) => k[k.length - 1][0]));
    }
  }
  prepare(MACRO, "macro");
  prepare(MICRO, "micro");

  function find(name) {
    const k = key(name);
    if (MACRO[k]) return { key: k, clip: MACRO[k] };
    if (MICRO[k]) return { key: k, clip: MICRO[k] };
    return null;
  }

  function emotion(name) {
    const k = key(name);
    if (k === "disaccordo") return { key: "disagree", pose: EMOTIONS.disagree };
    return EMOTIONS[k] ? { key: k, pose: EMOTIONS[k] } : null;
  }

  function catalog() {
    return { macro: Object.keys(MACRO), micro: Object.keys(MICRO), emozioni: Object.keys(EMOTIONS) };
  }

  H.Library = { find, emotion, catalog, HEAD };
})(window.Jarvis3D);
