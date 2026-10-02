(() => {
  const timers = new WeakMap();

  function lines(d) {
    const ly = d.lyrics || {};
    return Array.isArray(ly.synced) && ly.synced.length ? ly.synced : null;
  }

  function paint(el, d, ctx) {
    const synced = lines(d);
    const head = `<div class="ka-head">🎤 ${ctx.esc(d.title || "")}${d.artist ? ` — ${ctx.esc(d.artist)}` : ""}</div>`;
    if (!synced) {
      const plain = (d.lyrics && d.lyrics.plain) || "";
      el.innerHTML = head + (plain
        ? `<div class="ka-plain">${ctx.esc(plain)}</div>`
        : `<div class="ka-none">Testo non disponibile per questo brano.</div>`);
      return;
    }
    el.innerHTML = head + `<div class="ka-lines">${synced.map((l, i) =>
      `<div class="ka-line" data-i="${i}">${ctx.esc(l.text || "♪")}</div>`).join("")}</div>`;
    el._lines = synced;
    tick(el, d, ctx);
  }

  function tick(el, d, ctx) {
    const synced = el._lines;
    if (!synced || !d.started_at) return;
    const pos = ctx.now() - d.started_at;
    let cur = -1;
    for (let i = 0; i < synced.length; i++) { if (synced[i].t <= pos + 0.25) cur = i; else break; }
    const box = el.querySelector(".ka-lines");
    const nodes = el.querySelectorAll(".ka-line");
    nodes.forEach((n, i) => {
      n.classList.toggle("on", i === cur);
      n.classList.toggle("past", i < cur);
    });
    if (cur >= 0 && box && nodes[cur]) {
      const off = nodes[cur].offsetTop - box.clientHeight / 2 + nodes[cur].offsetHeight / 2;
      box.scrollTo({ top: Math.max(0, off), behavior: "smooth" });
    }
  }

  const impl = {
    render(el, d, ctx) {
      paint(el, d, ctx);
      clearInterval(timers.get(el));
      timers.set(el, setInterval(() => tick(el, el._d || d, ctx), 500));
      el._d = d;
    },
    update(el, d, ctx) {
      if (!el._d || el._d.key !== d.key) paint(el, d, ctx);
      el._d = d;
      tick(el, d, ctx);
    },
    destroy(el) { clearInterval(timers.get(el)); },
  };
  JarvisDesk.register("karaoke", impl);
})();
