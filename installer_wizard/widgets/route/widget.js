JarvisDesk.register("route", {
  render(el, d, ctx) {
    const delay = d.delay != null && d.delay >= 3 ? `<span class="ro-delay">+${d.delay} min traffico</span>`
      : d.traffic ? '<span class="ro-ok">traffico scorrevole</span>' : "";
    el.innerHTML = `<div class="ro-label">🚗 ${ctx.esc(d.mode || "viaggio")}</div>
      <div class="ro-title">${ctx.esc(d.title || "")}</div>
      <div class="ro-to">${ctx.esc(d.to || "")}</div>
      <div class="ro-main"><b>${ctx.esc(d.duration || "")}</b>${delay}</div>
      <div class="ro-meta">${ctx.esc(d.distance || "")}${d.via ? " · via " + ctx.esc(d.via) : ""}</div>
      <div class="ro-times">${d.leave_by ? `<div><small>Parti entro</small><b>${ctx.esc(d.leave_by)}</b></div>` : ""}
        <div><small>${d.leave_by ? "Appuntamento" : "Arrivo"}</small><b>${ctx.esc(d.arrive_at || "")}</b></div></div>`;
  },
});
