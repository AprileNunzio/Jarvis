(() => {
  const D = window.JarvisDisplay, { fmt } = D;
  const { render, wide } = D.stagePanels;
  const esc = fmt.esc;
  const pct = (v) => `${Math.max(0, Math.min(100, Number(v) * 100))}%`;

  render.annotated = (p) => {
    const boxes = (p.boxes || []).filter((b) => Array.isArray(b.box) && b.box.length === 4);
    return `<div class="v-shot"><img src="${esc(p.src)}" alt="">
      ${boxes.map((b, i) => `<div class="v-box ${esc(b.tone || "ok")}" style="left:${pct(b.box[0])};top:${pct(b.box[1])};width:${pct(b.box[2])};height:${pct(b.box[3])};animation-delay:${300 + i * 150}ms">
        <span>${esc(b.label || "")}</span></div>`).join("")}
      ${p.caption ? `<div class="v-cap">${esc(p.caption)}</div>` : ""}</div>`;
  };

  render.steps = (p) => `<ol class="v-steps">${(p.items || []).map((s, i) => `<li style="animation-delay:${i * 90}ms"><b>${i + 1}</b><span>${esc(s)}</span></li>`).join("")}</ol>`;

  render.chips = (p) => `<div class="v-chips">${(p.items || []).map((s) => `<span>${esc(s)}</span>`).join("")}</div>`;

  render.warn = (p) => `<div class="v-warn">${(p.items || []).map((s) => `<div>⚠️ <span>${esc(s)}</span></div>`).join("")}</div>`;

  Object.assign(wide, { annotated: 1 });
})();
