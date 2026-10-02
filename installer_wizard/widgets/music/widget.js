(() => {
  function paint(el, d, ctx) {
    const bio = (d.bio && d.bio.text) || "";
    el.innerHTML = `
      <div class="mu-label">${d.source === "spotify" ? "● Spotify" : "♪ In ascolto"}</div>
      <div class="mu-row">
        <div class="mu-cover" style="${d.cover ? `background-image:url('${ctx.esc(d.cover)}')` : ""}">${d.cover ? "" : "♪"}</div>
        <div class="mu-txt"><div class="mu-title">${ctx.esc(d.title)}</div><div class="mu-artist">${ctx.esc(d.artist || "")}</div>
          <div class="mu-meta">${ctx.esc([d.album, d.year, d.genre].filter(Boolean).join(" · "))}</div></div>
      </div>
      <div class="mu-prog"><span class="mu-track"><i></i></span><span class="mu-time"></span></div>
      ${bio ? `<div class="mu-bio">${ctx.esc(bio.length > 200 ? bio.slice(0, bio.lastIndexOf(" ", 200)) + "…" : bio)}</div>` : ""}`;
    tick(el, d, ctx);
  }
  function tick(el, d, ctx) {
    const bar = el.querySelector(".mu-track i"), time = el.querySelector(".mu-time");
    if (!bar) return;
    if (!d.duration || !d.started_at) { bar.parentNode.parentNode.style.display = "none"; return; }
    const pos = Math.max(0, Math.min(d.duration, ctx.now() - d.started_at));
    bar.style.width = `${(pos / d.duration) * 100}%`;
    time.textContent = `${ctx.mmss(pos)} / ${ctx.mmss(d.duration)}`;
  }
  const timers = new WeakMap();
  const impl = {
    render(el, d, ctx) { paint(el, d, ctx); clearInterval(timers.get(el)); timers.set(el, setInterval(() => tick(el, el._d || d, ctx), 1000)); el._d = d; },
    update(el, d, ctx) { if (!el._d || el._d.key !== d.key) paint(el, d, ctx); el._d = d; tick(el, d, ctx); },
    destroy(el) { clearInterval(timers.get(el)); },
  };
  JarvisDesk.register("music", impl);
})();
