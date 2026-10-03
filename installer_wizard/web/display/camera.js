(() => {
  const D = window.JarvisDisplay, { $, fmt } = D;
  const MINI = 250, MARGIN = 18, IDLE_OFF = 15 * 60000, ZOOM_MAX = 3, ZOOM_STEP = 0.25, FALLBACK_AFTER = 4000, SHOTS = 5;
  const KEY = "jarvis-cam-zone";
  const COLORS = ["#29e0ff", "#3dffa8", "#ffb547", "#ff4d6a", "#ffffff"];
  const cam = D.cam = { on: false, mirror: true, zoom: 1, draw: false, color: COLORS[0], zone: null, hidden: false, shots: [], source: "" };
  let root, video, ink, mini, bar, strip, flash, pen, stream, poll, feedTimer, lastStroke;

  const stored = () => { try { return JSON.parse(localStorage.getItem(KEY) || "null"); } catch (e) { return null; } };
  const keep = () => { try { localStorage.setItem(KEY, JSON.stringify({ x: cam.zone.x, y: cam.zone.y })); } catch (e) {} };
  const clampZone = (x, y) => ({
    x: Math.max(MARGIN, Math.min(window.innerWidth - MINI - MARGIN, x)),
    y: Math.max(MARGIN, Math.min(window.innerHeight - MINI - MARGIN, y)),
  });
  const zoneAt = (x, y) => { const p = clampZone(x, y); return { x: p.x, y: p.y, w: MINI, h: MINI, cx: p.x + MINI / 2, cy: p.y + MINI / 2 }; };

  function applyZone() {
    if (!cam.zone) return;
    D.stageZone = cam.hidden ? null : cam.zone;
    D.applyStage();
    mini.style.transform = `translate(${cam.zone.x}px, ${cam.zone.y}px)`;
    mini.classList.toggle("hidden", cam.hidden);
  }

  function build() {
    if (root) return;
    root = document.createElement("div");
    root.id = "cam-layer";
    root.innerHTML = '<div class="cam-stage"><img class="cam-video" alt=""><video class="cam-video" autoplay playsinline muted hidden></video></div><canvas class="cam-ink"></canvas><div class="cam-flash"></div>';
    document.body.appendChild(root);
    video = { img: root.querySelector("img.cam-video"), tag: root.querySelector("video.cam-video"), stage: root.querySelector(".cam-stage") };
    ink = root.querySelector(".cam-ink");
    flash = root.querySelector(".cam-flash");
    mini = document.createElement("div");
    mini.id = "cam-mini";
    mini.innerHTML = '<i class="cam-ring"></i>';
    document.body.appendChild(mini);
    bar = document.createElement("div");
    bar.id = "cam-bar";
    bar.innerHTML = [
      ["mirror", "↔", "Specchio"], ["zoom-out", "−", "Riduci"], ["zoom-in", "+", "Ingrandisci"], ["shot", "◉", "Scatta"],
      ["draw", "✎", "Disegna"], ["clear", "⌫", "Cancella disegno"], ["jarvis", "◌", "Mostra o nascondi Jarvis"], ["close", "✕", "Chiudi la webcam"],
    ].map(([a, g, t]) => `<button type="button" data-cam="${a}" title="${t}" aria-label="${t}">${g}</button>`).join("")
      + `<span class="cam-colors">${COLORS.map((c) => `<button type="button" data-color="${c}" style="--c:${c}" aria-label="Colore"></button>`).join("")}</span>`;
    document.body.appendChild(bar);
    strip = document.createElement("div");
    strip.id = "cam-shots";
    document.body.appendChild(strip);
    wire();
  }

  function size() {
    ink.width = window.innerWidth; ink.height = window.innerHeight;
    pen = ink.getContext("2d");
    pen.lineCap = pen.lineJoin = "round";
  }

  function wire() {
    size();
    window.addEventListener("resize", () => {
      if (!cam.on) return;
      const old = pen.getImageData(0, 0, ink.width, ink.height);
      size();
      pen.putImageData(old, 0, 0);
      cam.zone = zoneAt(cam.zone.x, cam.zone.y);
      applyZone();
    });
    bar.addEventListener("click", (e) => {
      const color = e.target.closest("[data-color]");
      if (color) { cam.color = color.dataset.color; setDraw(true); return paint(); }
      const b = e.target.closest("[data-cam]");
      if (b) act(b.dataset.cam);
    });
    wireDrag();
    wireInk();
  }

  function wireDrag() {
    let grab = null;
    mini.addEventListener("pointerdown", (e) => {
      grab = { dx: e.clientX - cam.zone.x, dy: e.clientY - cam.zone.y };
      mini.classList.add("grabbed");
      try { mini.setPointerCapture(e.pointerId); } catch (err) {}
    });
    mini.addEventListener("pointermove", (e) => {
      if (!grab) return;
      cam.zone = zoneAt(e.clientX - grab.dx, e.clientY - grab.dy);
      applyZone();
    });
    const drop = () => { if (!grab) return; grab = null; mini.classList.remove("grabbed"); keep(); };
    mini.addEventListener("pointerup", drop);
    mini.addEventListener("pointercancel", drop);
    mini.addEventListener("dblclick", () => act("jarvis"));
  }

  function wireInk() {
    ink.addEventListener("pointerdown", (e) => {
      if (!cam.draw) return;
      lastStroke = { x: e.clientX, y: e.clientY };
      try { ink.setPointerCapture(e.pointerId); } catch (err) {}
      dot(e.clientX, e.clientY);
    });
    ink.addEventListener("pointermove", (e) => {
      if (!cam.draw || !lastStroke) return;
      line(lastStroke, { x: e.clientX, y: e.clientY });
      lastStroke = { x: e.clientX, y: e.clientY };
    });
    const end = () => { lastStroke = null; };
    ink.addEventListener("pointerup", end);
    ink.addEventListener("pointercancel", end);
  }

  function stroke(draw) {
    pen.strokeStyle = pen.fillStyle = cam.color;
    pen.shadowColor = cam.color; pen.shadowBlur = 14; pen.lineWidth = 6;
    draw();
  }
  const dot = (x, y) => stroke(() => { pen.beginPath(); pen.arc(x, y, 3, 0, Math.PI * 2); pen.fill(); });
  const line = (a, b) => stroke(() => { pen.beginPath(); pen.moveTo(a.x, a.y); pen.lineTo(b.x, b.y); pen.stroke(); });

  function paint() {
    root.classList.toggle("mirror", cam.mirror);
    video.stage.style.setProperty("--zoom", cam.zoom);
    bar.querySelector('[data-cam="mirror"]').classList.toggle("on", cam.mirror);
    bar.querySelector('[data-cam="draw"]').classList.toggle("on", cam.draw);
    bar.querySelector('[data-cam="jarvis"]').classList.toggle("on", !cam.hidden);
    bar.classList.toggle("drawing", cam.draw);
    ink.classList.toggle("armed", cam.draw);
    bar.querySelectorAll("[data-color]").forEach((b) => b.classList.toggle("on", b.dataset.color === cam.color));
  }

  function setDraw(on) { cam.draw = on; paint(); }

  function act(name) {
    if (name === "mirror") cam.mirror = !cam.mirror;
    else if (name === "zoom-in") cam.zoom = Math.min(ZOOM_MAX, +(cam.zoom + ZOOM_STEP).toFixed(2));
    else if (name === "zoom-out") cam.zoom = Math.max(1, +(cam.zoom - ZOOM_STEP).toFixed(2));
    else if (name === "draw") cam.draw = !cam.draw;
    else if (name === "clear") pen.clearRect(0, 0, ink.width, ink.height);
    else if (name === "jarvis") { cam.hidden = !cam.hidden; applyZone(); }
    else if (name === "shot") shoot();
    else if (name === "close") return setCamera(false);
    paint();
  }

  function source() { return video.tag.hidden ? video.img : video.tag; }

  function frameBox(el) {
    const w = el.videoWidth || el.naturalWidth, h = el.videoHeight || el.naturalHeight;
    if (!w || !h) return null;
    const vw = window.innerWidth, vh = window.innerHeight, scale = Math.min(vw / w, vh / h);
    return { w, h, x: (vw - w * scale) / 2, y: (vh - h * scale) / 2, dw: w * scale, dh: h * scale };
  }

  function shoot() {
    const el = source(), box = frameBox(el);
    if (!box) return;
    const vw = window.innerWidth, vh = window.innerHeight, z = cam.zoom;
    const zw = box.dw * z, zh = box.dh * z, zx = vw / 2 + (box.x - vw / 2) * z, zy = vh / 2 + (box.y - vh / 2) * z;
    const rx = Math.max(0, zx), ry = Math.max(0, zy), rw = Math.min(vw, zx + zw) - rx, rh = Math.min(vh, zy + zh) - ry;
    if (rw < 8 || rh < 8) return;
    const k = box.w / zw, canvas = document.createElement("canvas");
    canvas.width = Math.round(rw * k); canvas.height = Math.round(rh * k);
    const g = canvas.getContext("2d");
    g.save();
    g.translate((zx - rx) * k, (zy - ry) * k);
    if (cam.mirror) { g.translate(zw * k, 0); g.scale(-1, 1); }
    g.drawImage(el, 0, 0, zw * k, zh * k);
    g.restore();
    g.drawImage(ink, rx, ry, rw, rh, 0, 0, canvas.width, canvas.height);
    flash.classList.remove("on"); void flash.offsetWidth; flash.classList.add("on");
    canvas.toBlob((blob) => { if (blob) addShot(URL.createObjectURL(blob)); }, "image/png");
  }

  function addShot(url) {
    cam.shots.unshift(url);
    while (cam.shots.length > SHOTS) URL.revokeObjectURL(cam.shots.pop());
    renderShots();
  }

  function renderShots() {
    strip.innerHTML = cam.shots.map((u, i) => `<a href="${fmt.esc(u)}" download="jarvis-${Date.now()}-${i + 1}.png" title="Salva la foto"><img src="${fmt.esc(u)}" alt="Foto ${i + 1}"></a>`).join("");
  }

  function useServerFeed() {
    video.tag.hidden = true; video.img.hidden = false;
    cam.source = "server";
    let live = false;
    video.img.onload = () => { live = true; };
    video.img.onerror = () => { if (cam.on) fallbackPolling(); };
    video.img.src = `/api/vision/live.mjpg?r=${Date.now()}`;
    feedTimer = setTimeout(() => { if (cam.on && !live && !video.img.naturalWidth) fallbackPolling(); }, FALLBACK_AFTER);
  }

  function fallbackPolling() {
    if (poll) return;
    video.img.onerror = null;
    cam.source = "server-snapshots";
    const next = () => { if (cam.on) video.img.src = `/api/vision/snapshot.jpg?t=${Date.now()}`; };
    video.img.onload = () => { if (cam.on) poll = setTimeout(next, 160); };
    video.img.onerror = () => { if (cam.on) poll = setTimeout(next, 1500); };
    poll = null;
    next();
  }

  async function useBrowserCamera() {
    if (!window.isSecureContext || !navigator.mediaDevices) return false;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" }, audio: false });
    } catch (err) { return false; }
    video.img.hidden = true; video.tag.hidden = false;
    video.tag.srcObject = stream;
    cam.source = "browser";
    return true;
  }

  function release() {
    clearTimeout(feedTimer); clearTimeout(poll); poll = null;
    if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
    if (video) { video.tag.srcObject = null; video.img.onload = video.img.onerror = null; video.img.removeAttribute("src"); }
  }

  async function setCamera(on) {
    if (on === cam.on) return;
    if (on) {
      build();
      cam.on = true;
      const saved = stored();
      cam.zone = zoneAt(saved ? saved.x : window.innerWidth - MINI - MARGIN, saved ? saved.y : window.innerHeight - MINI - MARGIN - 90);
      cam.prevZone = D.stageZone;
      document.body.classList.add("cam");
      cam.hidden = false;
      if (D.local || !(await useBrowserCamera())) useServerFeed();
      pen.clearRect(0, 0, ink.width, ink.height);
      paint();
      applyZone();
      cam.lastSeen = Date.now();
    } else {
      cam.on = false;
      release();
      document.body.classList.remove("cam");
      cam.draw = false;
      D.stageZone = cam.prevZone || null;
      D.applyStage();
      cam.shots.splice(0).forEach((u) => URL.revokeObjectURL(u));
      if (strip) strip.innerHTML = "";
    }
  }

  D.setCamera = setCamera;
  D.startCamera = () => {
    setInterval(() => {
      if (!cam.on) return;
      const touched = Date.now() - D.lastInteraction < IDLE_OFF || document.querySelector(".hand-cursor.on");
      if (touched) cam.lastSeen = Date.now();
      else if (Date.now() - cam.lastSeen > IDLE_OFF) setCamera(false);
    }, 30000);
  };
})();
