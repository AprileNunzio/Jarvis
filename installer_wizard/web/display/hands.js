(() => {
  const D = window.JarvisDisplay;
  const V = window.JARVIS_ASSET_V ? `?v=${window.JARVIS_ASSET_V}` : "";
  const PINCH_ON = 0.32, PINCH_OFF = 0.5, IDLE_FPS = 4, BUDGET = 0.25, WARMUP = 3, PROBE = 12, MEMORY = 86400000, BOX = { x0: 0.12, x1: 0.88, y0: 0.08, y1: 0.78 };
  const FLICK = 2.2, POINTER = 77;
  const st = { model: null, img: null, cursor: null, last: 0, ts: 0, x: 0, y: 0, seen: 0, pinch: false, target: null,
               trail: [], pair: null, failures: 0, cost: 0, delegate: "", samples: 0, probe: 0, status: "spente", stopped: false };
  const opt = () => D.FACE || {};
  const VERDICT = "jarvis.hands.verdict";

  const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const clamp = (v) => Math.max(0, Math.min(1, v));

  function cursor() {
    const el = document.createElement("div");
    el.className = "hand-cursor";
    el.innerHTML = "<i></i>";
    document.body.appendChild(el);
    return el;
  }

  async function createModel(vision, delegate) {
    const fileset = { wasmLoaderPath: `/vendor/vision_wasm_internal.js${V}`, wasmBinaryPath: `/vendor/vision_wasm_internal.wasm${V}` };
    return vision.HandLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: `/vendor/hand_landmarker.task${V}`, delegate },
      runningMode: "VIDEO", numHands: opt().hands_count || 2, minHandDetectionConfidence: 0.6, minHandPresenceConfidence: 0.6, minTrackingConfidence: 0.5,
    });
  }

  function fire(type, target, x, y, extra = {}) {
    if (!target) return;
    target.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, composed: true, pointerId: POINTER,
      pointerType: "mouse", isPrimary: true, button: 0, buttons: type === "pointerup" ? 0 : 1, clientX: x, clientY: y, ...extra }));
  }

  function pointAt(x, y) {
    st.cursor.style.display = "none";
    const el = document.elementFromPoint(x, y);
    st.cursor.style.display = "";
    return el;
  }

  function press(x, y) {
    const el = pointAt(x, y);
    if (!el) return;
    const clickable = el.closest("button, a, [data-a], [data-ns], input[type=checkbox]");
    if (clickable && !clickable.closest(".v3-stage canvas")) { clickable.click(); st.target = null; return; }
    st.target = el.closest(".v3-stage canvas, canvas#scene") || el.closest(".desk > .widget") || el;
    fire("pointerdown", st.target, x, y);
    st.trail = [{ x, y, t: performance.now() }];
  }

  function drag(x, y) {
    if (!st.target) return;
    fire("pointermove", st.target, x, y);
    st.trail.push({ x, y, t: performance.now() });
    st.trail = st.trail.filter((p) => performance.now() - p.t < 160);
  }

  function release(x, y) {
    if (!st.target) return;
    const a = st.trail[0], b = st.trail[st.trail.length - 1], W = window.innerWidth;
    const vx = a && b && b.t > a.t ? (b.x - a.x) / W / ((b.t - a.t) / 1000) : 0;
    if (Math.abs(vx) > FLICK && st.target.matches(".desk > .widget")) {
      const edge = vx > 0 ? W - 4 : 4;
      fire("pointermove", st.target, edge, y);
      fire("pointerup", st.target, edge, y);
    } else {
      fire("pointerup", st.target, x, y);
    }
    st.target = null;
  }

  function zoom(hands) {
    const pts = hands.map((h) => ({ x: (h[4].x + h[8].x) / 2, y: (h[4].y + h[8].y) / 2 }));
    const span = dist(pts[0], pts[1]);
    if (st.pair) {
      const canvas = pointAt(st.x, st.y);
      const target = canvas && canvas.closest(".v3-stage canvas");
      if (target) target.dispatchEvent(new WheelEvent("wheel", { bubbles: true, cancelable: true, deltaY: (st.pair - span) * 2400,
        clientX: st.x, clientY: st.y }));
    }
    st.pair = span;
  }

  function track(lm) {
    const palm = dist(lm[0], lm[9]) || 0.1;
    const ratio = dist(lm[4], lm[8]) / palm;
    const tip = st.pinch || ratio < PINCH_ON ? { x: (lm[4].x + lm[8].x) / 2, y: (lm[4].y + lm[8].y) / 2 } : lm[8];
    const W = window.innerWidth, H = window.innerHeight;
    const tx = clamp((1 - tip.x - BOX.x0) / (BOX.x1 - BOX.x0)) * W, ty = clamp((tip.y - BOX.y0) / (BOX.y1 - BOX.y0)) * H;
    const k = st.seen && performance.now() - st.seen < 400 ? 0.45 : 1;
    st.x += (tx - st.x) * k; st.y += (ty - st.y) * k;
    st.seen = performance.now();
    if (!st.pinch && ratio < PINCH_ON) { st.pinch = true; press(st.x, st.y); }
    else if (st.pinch && ratio > PINCH_OFF) { st.pinch = false; release(st.x, st.y); }
    else if (st.pinch) drag(st.x, st.y);
    st.cursor.style.transform = `translate(${st.x}px, ${st.y}px)`;
    st.cursor.classList.toggle("pinch", st.pinch);
    st.cursor.classList.add("on");
    D.lastInteraction = Date.now();
  }

  function remember(reason) {
    try { localStorage.setItem(VERDICT, JSON.stringify({ gpu: window.jarvisPerf && window.jarvisPerf.gpu, max: opt().hands_max_ms, reason, at: Date.now() })); } catch (err) { }
  }

  function recalled() {
    try {
      const v = JSON.parse(localStorage.getItem(VERDICT) || "null");
      return v && v.gpu === (window.jarvisPerf && window.jarvisPerf.gpu) && v.max === opt().hands_max_ms && Date.now() - v.at < MEMORY ? v.reason : "";
    } catch (err) { return ""; }
  }

  function stop(reason, keep) {
    st.stopped = true;
    st.status = `spente: ${reason}`;
    if (st.img) { st.img.onerror = null; st.img.src = ""; st.img.remove(); }
    if (st.cursor) st.cursor.classList.remove("on", "pinch");
    if (keep) remember(reason);
    console.warn(`Comandi con le mani spenti: ${reason}`);
  }

  function judge(spent) {
    st.samples++;
    if (opt().hands !== "auto" || st.samples <= WARMUP) return;
    const max = opt().hands_max_ms || 50;
    if (st.samples <= WARMUP + PROBE) {
      st.probe += spent;
      if (st.samples === WARMUP + PROBE) {
        const avg = st.probe / PROBE;
        if (avg > max) stop(`GPU troppo lenta (${Math.round(avg)} ms per analisi, massimo ${max})`, true);
        else st.status = `attive (${Math.round(avg)} ms per analisi, ${st.delegate})`;
      }
    } else if (st.cost > max * 2) {
      stop(`la pagina rallentava (${Math.round(st.cost)} ms per analisi)`, true);
    }
  }

  function loop(now) {
    if (st.stopped) return;
    requestAnimationFrame(loop);
    const idle = !st.seen || now - st.seen > 5000;
    const gap = Math.max(1000 / (idle ? IDLE_FPS : opt().hands_fps || 20), st.cost / BUDGET);
    if (now - st.last < gap || !st.img.naturalWidth) return;
    st.last = now;
    let res;
    st.ts = Math.max(st.ts + 1, Math.round(now));
    const t0 = performance.now();
    try { res = st.model.detectForVideo(st.img, st.ts); }
    catch (err) { if (++st.failures === 1) console.warn("Mani: fotogramma non elaborato", err); return; }
    const spent = performance.now() - t0;
    st.cost = st.cost ? st.cost * 0.8 + spent * 0.2 : spent;
    if (window.jarvisPerf) window.jarvisPerf.cost(`mani_${st.delegate}`, spent);
    judge(spent);
    if (st.stopped) return;
    const hands = res.landmarks || [];
    if (hands.length) {
      track(hands[0]);
      if (hands.length === 2 && hands.every((h) => dist(h[4], h[8]) / (dist(h[0], h[9]) || 0.1) < PINCH_ON)) zoom(hands);
      else st.pair = null;
    } else if (st.seen && now - st.seen > 700) {
      if (st.pinch) { st.pinch = false; release(st.x, st.y); }
      st.cursor.classList.remove("on", "pinch");
      st.pair = null;
    }
  }

  async function start() {
    const mode = opt().hands;
    if (!D.local) { st.status = "spente: solo sul display del server"; return; }
    if (!mode || mode === "0" || mode === false) { st.status = "spente: disattivate nelle funzionalità"; return; }
    const auto = mode === "auto";
    const gpu = (window.jarvisPerf && window.jarvisPerf.gpu) || "";
    if (auto && /swiftshader|llvmpipe|software|nessuna/i.test(gpu)) { st.status = `spente: nessuna GPU utilizzabile (${gpu})`; return; }
    const known = auto && recalled();
    if (known) { st.status = `spente: ${known} (verifica già fatta, riprovo tra 24 ore)`; return; }
    st.status = "prova della GPU in corso";
    try {
      const vision = await import(`/vendor/vision_bundle.mjs${V}`);
      try { st.model = await createModel(vision, "GPU"); st.delegate = "gpu"; }
      catch (err) {
        if (auto) { stop("la GPU non accetta il riconoscimento", true); return; }
        st.model = await createModel(vision, "CPU"); st.delegate = "cpu";
      }
    } catch (err) {
      stop("modello non caricato", false);
      return;
    }
    st.cursor = cursor();
    st.img = new Image();
    st.img.className = "hand-feed";
    document.body.appendChild(st.img);
    st.img.onerror = () => setTimeout(() => { if (!st.stopped) st.img.src = `/api/vision/hands.mjpg?r=${Date.now()}`; }, 10000);
    st.img.src = "/api/vision/hands.mjpg";
    st.x = window.innerWidth / 2; st.y = window.innerHeight / 2;
    if (!auto) st.status = `attive per tua scelta (${st.delegate})`;
    requestAnimationFrame(loop);
  }

  window.jarvisHands = { get status() { return st.status; } };
  D.startHands = () => setTimeout(start, 4000);
})();
