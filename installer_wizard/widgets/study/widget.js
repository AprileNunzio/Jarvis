JarvisDesk.register("study", {
  render(el, d, ctx) {
    el.innerHTML = `<div class="st-row"><span class="st-ic">🎓</span><div><div class="st-t">${ctx.esc(d.topic || "Studio autonomo")}${d.level ? ` · ${ctx.esc(d.level)}` : ""}</div>
      <div class="st-d">${ctx.esc(d.detail || "")}</div></div></div>`;
  },
});
