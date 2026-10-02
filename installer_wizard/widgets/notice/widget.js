JarvisDesk.register("notice", {
  render(el, d, ctx) {
    el.innerHTML = `<div class="no-row"><span class="no-ic">${ctx.esc(d.icon || "🔔")}</span><div><div class="no-t">${ctx.esc(d.title || "")}</div>
      <div class="no-x">${ctx.esc(d.text || "")}</div></div></div>`;
    el.parentNode && el.parentNode.classList.toggle("no-warn", d.level === "warn");
  },
});
