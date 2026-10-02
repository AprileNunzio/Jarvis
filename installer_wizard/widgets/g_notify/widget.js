(() => {
  const timers = new Map();
  const R = 26, C = 2 * Math.PI * R;

  function countdown(el, at, ctx) {
    const left = Math.max(0, at - ctx.now());
    const span = el.querySelector(".gn-left"), arc = el.querySelector(".gn-arc");
    if (span) span.textContent = left >= 3600 ? `${Math.floor(left / 3600)}h ${Math.floor((left % 3600) / 60)}m` : ctx.mmss(left);
    if (arc) arc.style.strokeDashoffset = `${C * (1 - Math.min(1, left / 1800))}`;
  }

  function body(d, ctx) {
    if (d.kind === "event") {
      return `<div class="gn-row"><svg class="gn-ring" viewBox="0 0 64 64"><circle cx="32" cy="32" r="${R}" class="bg"/>
          <circle cx="32" cy="32" r="${R}" class="gn-arc" stroke-dasharray="${C}"/></svg>
        <div class="gn-main"><div class="gn-who">${ctx.esc(d.who || "")} · tra <b class="gn-left"></b></div>
          <div class="gn-title">${ctx.esc(d.title || "")}</div>${d.text ? `<div class="gn-text">📍 ${ctx.esc(d.text)}</div>` : ""}</div></div>`;
    }
    if (d.kind === "brief") {
      return `<div class="gn-who">${ctx.esc(d.who || "")} · la tua giornata</div>
        <div class="gn-stats">${(d.items || []).map((x) => `<div><span>${ctx.esc(x.icon)}</span><b>${ctx.esc(x.value)}</b><small>${ctx.esc(x.label)}</small></div>`).join("")}</div>
        ${(d.groups || []).map((g) => `<div class="gn-group gn-${ctx.esc(g.key)}"><div class="gn-glabel">${ctx.esc(g.icon)} ${ctx.esc(g.label)}</div>
          ${g.entries.slice(0, 4).map((e) => `<div class="gn-entry">${e.time ? `<b>${ctx.esc(e.time)}</b>` : ""}<span>${ctx.esc(e.title)}</span>${e.where ? `<small>📍 ${ctx.esc(e.where)}</small>` : ""}</div>`).join("")}
          ${g.entries.length > 4 ? `<div class="gn-more">e altri ${g.entries.length - 4}</div>` : ""}</div>`).join("")}
        ${d.text && !(d.groups || []).length ? `<div class="gn-text">${ctx.esc(d.text)}</div>` : ""}`;
    }
    return `<div class="gn-row"><span class="gn-ic">${ctx.esc(d.icon || "✉️")}</span><div class="gn-main">
        <div class="gn-who">${ctx.esc(d.who || "")}${d.from ? ` · da ${ctx.esc(d.from)}` : ""}</div>
        <div class="gn-title">${ctx.esc(d.title || "")}</div>${d.text ? `<div class="gn-text">${ctx.esc(d.text)}</div>` : ""}</div></div>`;
  }

  function render(el, d, ctx) {
    clearInterval(timers.get(el));
    el.innerHTML = `<div class="gn gn-${ctx.esc(d.kind || "mail")}">${body(d, ctx)}</div>`;
    if (d.kind === "event" && d.at) {
      countdown(el, d.at, ctx);
      timers.set(el, setInterval(() => countdown(el, d.at, ctx), 1000));
    }
  }

  JarvisDesk.register("g_notify", { render, update: render, destroy(el) { clearInterval(timers.get(el)); } });
})();
