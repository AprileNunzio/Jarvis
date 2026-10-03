(() => {
  const impls = {}, loading = {}, cards = new Map();
  let host = null, resizeObs = null, lastList = [], allList = [], layoutRaf = 0, lastZone = "", screens = [];
  const hooks = { speak: () => {}, onStage: () => {}, screen: 0, satellite: false };
  const EDGE = 28;

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function postPos(id, x, y) {
    fetch("/api/desk/position", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(y === null ? { id, clear: true } : { id, x, y }) }).catch(() => {});
  }
  function neighbor(dir) {
    const i = screens.findIndex((s) => s.n === hooks.screen);
    return i < 0 ? null : screens[i + dir] || null;
  }
  function moveTo(id, n) {
    const card = [...cards.values()].find((c) => c.inst.id === id);
    if (card) card.el.classList.add(n > hooks.screen ? "fly-right" : "fly-left");
    return fetch("/api/desk/screen", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, screen: n }) }).catch(() => {});
  }
  function edgeDrop(card, x) {
    const W = window.innerWidth, dir = x < EDGE ? -1 : x > W - EDGE ? 1 : 0, target = dir && neighbor(dir);
    if (!target) return false;
    moveTo(card.inst.id, target.n);
    return true;
  }
  function edgeHint(x) {
    const W = window.innerWidth, b = document.body;
    b.classList.toggle("edge-l", x !== null && x < EDGE * 3 && !!neighbor(-1));
    b.classList.toggle("edge-r", x !== null && x > W - EDGE * 3 && !!neighbor(1));
  }
  function enableDrag(card) {
    const el = card.el;
    let sx, sy, ox, oy, moved;
    el.addEventListener("pointerdown", (e) => {
      if (e.button || e.target.closest("button, input, select, textarea, a")) return;
      sx = e.clientX; sy = e.clientY; ox = el.offsetLeft; oy = el.offsetTop; moved = false;
      try { el.setPointerCapture(e.pointerId); } catch (err) {}
      const move = (ev) => {
        const dx = ev.clientX - sx, dy = ev.clientY - sy;
        if (!moved && Math.hypot(dx, dy) < 6) return;
        moved = true; el.classList.add("dragging");
        el.style.left = `${ox + dx}px`; el.style.top = `${oy + dy}px`;
        edgeHint(ev.clientX);
      };
      const up = (ev) => {
        el.removeEventListener("pointermove", move); el.removeEventListener("pointerup", up);
        el.classList.remove("dragging");
        edgeHint(null);
        if (!moved) return;
        if (edgeDrop(card, ev.clientX)) return;
        const W = window.innerWidth, H = window.innerHeight;
        const cx = (el.offsetLeft + el.offsetWidth / 2) / W, cy = (el.offsetTop + el.offsetHeight / 2) / H;
        card.inst.pos = { x: cx, y: cy };
        postPos(card.inst.id, cx, cy);
        scheduleLayout();
      };
      el.addEventListener("pointermove", move); el.addEventListener("pointerup", up);
    });
    el.addEventListener("dblclick", () => {
      if (!card.inst.pos) return;
      card.inst.pos = null; postPos(card.inst.id, null, null); scheduleLayout();
    });
  }
  const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  const ctx = { esc, mmss, speak: (t) => hooks.speak(t), now: () => Date.now() / 1000 };

  function load(inst) {
    const key = `${inst.id}@${inst.rev}`;
    if (impls[inst.id] && impls[inst.id].rev === inst.rev) return Promise.resolve(impls[inst.id]);
    if (loading[key]) return loading[key];
    if (inst.css && !document.querySelector(`link[data-widget="${inst.id}"][data-rev="${inst.rev}"]`)) {
      const l = document.createElement("link");
      l.rel = "stylesheet"; l.href = `/widgets/${inst.id}/widget.css?r=${inst.rev}`; l.dataset.widget = inst.id; l.dataset.rev = inst.rev;
      document.head.appendChild(l);
    }
    loading[key] = new Promise((ok, ko) => {
      const s = document.createElement("script");
      s.src = `/widgets/${inst.id}/widget.js?r=${inst.rev}`;
      s.onload = () => (impls[inst.id] ? (impls[inst.id].rev = inst.rev, ok(impls[inst.id])) : ko(new Error(`widget ${inst.id} non registrato`)));
      s.onerror = () => ko(new Error(`widget ${inst.id} non caricato`));
      document.head.appendChild(s);
    });
    return loading[key];
  }

  async function draw(inst) {
    let card = cards.get(inst.key);
    const sig = JSON.stringify(inst.data);
    if (card && card.sig === sig && card.rev === inst.rev) { card.inst = inst; return card; }
    let impl;
    try { impl = await load(inst); } catch (err) { console.warn(err); return null; }
    if (!card || card.rev !== inst.rev) {
      if (card) remove(inst.key, true);
      const el = document.createElement("section");
      el.className = `widget size-${inst.size} w-${inst.id}${inst.takeover ? " takeover" : ""}${inst.chrome === false ? " frameless" : ""} hidden`;
      el.dataset.key = inst.key;
      el.innerHTML = '<div class="w-body"></div>';
      card = { el, sig, rev: inst.rev, impl, inst, placed: false };
      cards.set(inst.key, card);
      host.appendChild(el);
      enableDrag(card);
      if (resizeObs) resizeObs.observe(el);
      try { impl.render(el.firstChild, inst.data, ctx); } catch (err) { console.warn(`widget ${inst.id}:`, err); }
      if ((inst.takeover || (inst.data && inst.data.announce)) && inst.data && inst.data.speak) ctx.speak(inst.data.speak);
    } else {
      card.sig = sig; card.inst = inst;
      try { (impl.update || impl.render)(card.el.firstChild, inst.data, ctx); } catch (err) { console.warn(`widget ${inst.id}:`, err); }
    }
    return card;
  }

  function remove(key, now) {
    const card = cards.get(key);
    if (!card) return;
    cards.delete(key);
    try { card.impl.destroy && card.impl.destroy(card.el.firstChild); } catch (e) {}
    if (now) { card.el.remove(); return; }
    card.el.classList.add("leave");
    setTimeout(() => card.el.remove(), 450);
  }

  const place = (card, x, y, w, h) => {
    const s = card.el.style;
    s.left = `${Math.round(x)}px`; s.top = `${Math.round(y)}px`; s.width = `${Math.round(w)}px`;
    s.height = h ? `${Math.round(h)}px` : "";
    card.el.classList.remove("hidden");
    if (!card.placed) {
      card.placed = true;
      card.el.classList.add("enter");
      card.el.addEventListener("animationend", () => card.el.classList.remove("enter"), { once: true });
    }
  };
  function covers(cards, W, H) {
    const r = Math.min(W, H) * 0.36, cx = W / 2, cy = H * 0.46;
    return cards.some((c) => {
      if (c.el.classList.contains("hidden")) return false;
      const x0 = c.el.offsetLeft, y0 = c.el.offsetTop, x1 = x0 + c.el.offsetWidth, y1 = y0 + c.el.offsetHeight;
      const nx = Math.max(x0, Math.min(cx, x1)), ny = Math.max(y0, Math.min(cy, y1));
      return (nx - cx) ** 2 + (ny - cy) ** 2 < r * r;
    });
  }
  const PIN_GAP = 14;
  const hits = (a, b) => a.x < b.x + b.w + PIN_GAP && a.x + a.w + PIN_GAP > b.x && a.y < b.y + b.h + PIN_GAP && a.y + a.h + PIN_GAP > b.y;
  function clearSpot(want, blocked, box) {
    let spot = { x: want.x, y: want.y };
    for (let n = 0; n < blocked.length * 2 + 2; n++) {
      const o = blocked.find((b) => hits({ x: spot.x, y: spot.y, w: want.w, h: want.h }, b));
      if (!o) return spot;
      const options = [
        { x: spot.x, y: o.y + o.h + PIN_GAP }, { x: spot.x, y: o.y - want.h - PIN_GAP },
        { x: o.x + o.w + PIN_GAP, y: spot.y }, { x: o.x - want.w - PIN_GAP, y: spot.y },
      ].filter((p) => p.x >= box.x0 && p.x + want.w <= box.x1 && p.y >= box.y0 && p.y + want.h <= box.y1);
      if (!options.length) return spot;
      options.sort((a, b) => Math.hypot(a.x - want.x, a.y - want.y) - Math.hypot(b.x - want.x, b.y - want.y));
      spot = options[0];
    }
    return spot;
  }
  const measure = (card, w) => { card.el.style.width = `${Math.round(w)}px`; card.el.style.height = ""; return card.el.offsetHeight; };

  function layoutGrid() {
    const W = window.innerWidth, H = window.innerHeight, M = 26, GAP = 16, TOP = 96, BOTTOM = H - 30;
    const cols = Math.max(1, Math.floor((W - 2 * M + GAP) / 420)), colW = (W - 2 * M - GAP * (cols - 1)) / cols;
    const heights = Array(cols).fill(TOP);
    const ordered = lastList.map((i) => cards.get(i.key)).filter(Boolean);
    const takeover = ordered.find((c) => c.inst.takeover);
    for (const c of ordered) {
      c.el.classList.remove("pinned");
      if (takeover && c !== takeover) { c.el.classList.add("hidden"); continue; }
      if (c === takeover) { place(c, M, TOP, W - 2 * M, BOTTOM - TOP); continue; }
      const fit = (span) => {
        let col = 0, best = Infinity;
        for (let i = 0; i + span <= cols; i++) {
          const top = Math.max(...heights.slice(i, i + span));
          if (top < best) { best = top; col = i; }
        }
        const w = colW * span + GAP * (span - 1);
        return { span, col, best, w, h: measure(c, w) };
      };
      const wide = c.inst.size === "full" ? cols : c.inst.size === "l" ? Math.min(2, cols) : 1;
      let f = fit(wide);
      if (f.best + f.h > BOTTOM && wide > 1) f = fit(1);
      const { span, col, best, w, h } = f;
      if (best + h > BOTTOM && best > TOP) { c.el.classList.add("hidden"); continue; }
      place(c, M + col * (colW + GAP), best, w, c.inst.size === "full" ? BOTTOM - best : 0);
      for (let i = col; i < col + span; i++) heights[i] = best + (c.inst.size === "full" ? BOTTOM : h) + GAP;
    }
    document.body.classList.toggle("desk-has", ordered.length > 0);
    document.body.classList.toggle("desk-alert", !!takeover);
  }

  function layout() {
    if (hooks.satellite) { layoutGrid(); return; }
    const W = window.innerWidth, H = window.innerHeight;
    const M = W < 700 ? 14 : 26, GAP = 14, TOP = W < 700 ? 110 : 124, BOTTOM = H - (W < 700 ? 96 : 104);
    const ordered = lastList.map((i) => cards.get(i.key)).filter(Boolean);
    const takeover = ordered.find((c) => c.inst.takeover);
    const pinned = ordered.filter((c) => c.inst.pos && !c.inst.takeover);
    const normal = ordered.filter((c) => !c.inst.takeover && !c.inst.pos);
    const portrait = W < H || W < 760;
    let zone = null;
    ordered.forEach((c) => c.el.classList.remove("pinned"));

    const blocked = [];
    for (const c of pinned) {
      if (takeover) { c.el.classList.add("hidden"); continue; }
      const w = Math.max(240, Math.min(400, W * 0.26));
      const h = measure(c, w);
      const x = Math.max(M, Math.min(W - M - w, c.inst.pos.x * W - w / 2));
      const y = Math.max(TOP, Math.min(BOTTOM - h, c.inst.pos.y * H - h / 2));
      const spot = clearSpot({ x, y, w, h }, blocked, { x0: M, y0: TOP, x1: W - M, y1: BOTTOM });
      place(c, spot.x, spot.y, w);
      blocked.push({ x: spot.x, y: spot.y, w, h });
      c.el.classList.add("pinned");
    }

    if (takeover) {
      normal.forEach((c) => c.el.classList.add("hidden"));
      if (portrait) {
        const top = Math.round(H * 0.36);
        place(takeover, M, top, W - 2 * M, BOTTOM - top);
        zone = { x: M, y: TOP - 20, w: W - 2 * M, h: top - TOP - 50 };
      } else {
        const left = Math.round(W * 0.36);
        place(takeover, left, TOP, W - left - M, BOTTOM - TOP);
        zone = { x: M, y: TOP, w: left - M - GAP, h: BOTTOM - TOP - 60 };
      }
    } else if (normal.length && portrait) {
      const cols = W >= 560 ? 2 : 1, colW = (W - 2 * M - GAP * (cols - 1)) / cols, limit = TOP + (H - TOP) * 0.42;
      const heights = Array(cols).fill(BOTTOM);
      for (const c of normal) {
        const h = measure(c, colW);
        const col = heights.indexOf(Math.max(...heights));
        const x = M + col * (colW + GAP);
        let y = heights[col] - h;
        for (let n = 0; n <= blocked.length; n++) {
          const o = blocked.find((b) => hits({ x, y, w: colW, h }, b));
          if (!o) break;
          y = o.y - h - PIN_GAP;
        }
        if (y < limit) { c.el.classList.add("hidden"); continue; }
        heights[col] = y - GAP;
        place(c, x, y, colW);
      }
      const used = Math.min(...heights);
      zone = { x: M, y: TOP - 20, w: W - 2 * M, h: Math.max(160, used - TOP - 50) };
    } else if (normal.length) {
      const colW = Math.max(280, Math.min(400, W * 0.26));
      const cols = { right: TOP, left: TOP };
      let usedLeft = false, usedRight = false;
      const slot = (side, h) => {
        const x = side === "right" ? W - M - colW : M;
        let y = cols[side];
        for (let n = 0; n <= blocked.length; n++) {
          const o = blocked.find((b) => hits({ x, y, w: colW, h }, b));
          if (!o) break;
          y = o.y + o.h + PIN_GAP;
        }
        return { x, y };
      };
      for (const c of normal) {
        const h = measure(c, colW);
        const right = slot("right", h), left = slot("left", h);
        const side = right.y + h <= BOTTOM || !usedRight ? "right" : left.y + h <= BOTTOM || !usedLeft ? "left" : null;
        const spot = side === "right" ? right : left;
        if (!side || spot.y + h > BOTTOM + 40) { c.el.classList.add("hidden"); continue; }
        place(c, spot.x, spot.y, colW);
        cols[side] = spot.y + h + GAP;
        if (side === "right") usedRight = true; else usedLeft = true;
      }
      const x0 = usedLeft ? M + colW + GAP * 2 : M, x1 = usedRight ? W - M - colW - GAP * 2 : W - M;
      zone = { x: x0, y: TOP - 30, w: x1 - x0, h: BOTTOM - TOP - 70 };
    }

    if (!takeover && zone && !covers(normal, W, H)) zone = null;
    document.body.classList.toggle("desk-has", normal.length > 0 || !!takeover);
    document.body.classList.toggle("desk-alert", !!takeover);
    const stage = zone ? { ...zone, cx: zone.x + zone.w / 2, cy: zone.y + zone.h / 2 } : null;
    const sig = JSON.stringify(stage);
    if (sig !== lastZone) { lastZone = sig; hooks.onStage(stage); }
  }
  const scheduleLayout = () => { cancelAnimationFrame(layoutRaf); layoutRaf = requestAnimationFrame(layout); };

  const mine = (i) => i.screen === -1 || (i.screen == null ? hooks.screen === 0 : i.screen === hooks.screen);

  async function render(list) {
    allList = list || [];
    lastList = allList.filter(mine);
    if (!host) return;
    const live = new Set(lastList.map((i) => i.key));
    [...cards.keys()].filter((k) => !live.has(k)).forEach((k) => remove(k));
    for (const inst of lastList) await draw(inst);
    scheduleLayout();
  }

  function hello() {
    fetch("/api/desk/hello", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ screen: hooks.screen, x: hooks.x || 0, w: window.innerWidth, h: window.innerHeight,
        local: ["127.0.0.1", "localhost"].includes(location.hostname), ear: window.jarvisEar ? `${window.jarvisEar.state} ${window.jarvisEar.link}` : "",
        perf: window.jarvisPerf ? window.jarvisPerf.text : "" }) }).catch(() => {});
  }

  function mount(container, options = {}) {
    host = container;
    Object.assign(hooks, options);
    hello();
    setInterval(hello, 10000);
    ["l", "r"].forEach((side) => { const g = document.createElement("div"); g.className = `edge-glow ${side}`; document.body.appendChild(g); });
    window.addEventListener("resize", scheduleLayout);
    if (window.ResizeObserver) resizeObs = new ResizeObserver(scheduleLayout);
    render(allList);
  }

  window.JarvisDesk = {
    register(id, impl) { impls[id] = impl; },
    mount, render, relayout: scheduleLayout, moveTo, neighbor,
    setScreens(list) { screens = list || []; document.body.classList.toggle("multi-screen", screens.length > 1); },
    cardAt(x, y) {
      const el = document.elementFromPoint(x, y), sec = el && el.closest(".desk > .widget");
      return sec ? cards.get(sec.dataset.key) || null : null;
    },
    get screen() { return hooks.screen; },
    get active() { return lastList; },
    get all() { return allList; },
  };
})();
