JarvisDesk.register("brief", {
  render(el, d, ctx) {
    const image = d.image && d.image.src
      ? `<figure class="br-fig"><img src="${ctx.esc(d.image.src)}" alt="${ctx.esc(d.title || "")}">${d.image.credit ? `<figcaption>${ctx.esc(d.image.credit)}</figcaption>` : ""}</figure>`
      : "";
    const lines = (d.lines || []).map((l) => `<li>${ctx.esc(l)}</li>`).join("");
    el.innerHTML = `<div class="br-card">${d.title ? `<div class="br-title">${ctx.esc(d.title)}</div>` : ""}${image}${lines ? `<ul class="br-lines">${lines}</ul>` : ""}</div>`;
  },
});
