(() => {
  const D = window.JarvisDisplay, { $, fmt } = D;
  const ICONS = {
    clear: '<circle cx="24" cy="24" r="9" fill="#ffc53d"/><g stroke="#ffc53d" stroke-width="2.5" stroke-linecap="round"><path d="M24 5v5M24 38v5M5 24h5M38 24h5M10.5 10.5l3.5 3.5M34 34l3.5 3.5M10.5 37.5l3.5-3.5M34 14l3.5-3.5"/></g>',
    partly: '<circle cx="18" cy="18" r="7" fill="#ffc53d"/><path d="M15 36h20a7 7 0 0 0 0-14 9 9 0 0 0-17 2 6 6 0 0 0-3 12z" fill="#9fc6dc"/>',
    cloudy: '<path d="M12 36h24a8 8 0 0 0 0-16 10 10 0 0 0-19 2 7 7 0 0 0-5 14z" fill="#9fc6dc"/>',
    fog: '<path d="M12 28h24a8 8 0 0 0 0-16 10 10 0 0 0-19 2 7 7 0 0 0-5 14z" fill="#7fa3b8"/><g stroke="#7fa3b8" stroke-width="2.5" stroke-linecap="round"><path d="M10 34h28M14 40h20"/></g>',
    drizzle: '<path d="M12 30h24a8 8 0 0 0 0-16 10 10 0 0 0-19 2 7 7 0 0 0-5 14z" fill="#9fc6dc"/><g stroke="#3d9bff" stroke-width="2.5" stroke-linecap="round"><path d="M18 35v3M26 35v3M34 35v3"/></g>',
    rain: '<path d="M12 28h24a8 8 0 0 0 0-16 10 10 0 0 0-19 2 7 7 0 0 0-5 14z" fill="#9fc6dc"/><g stroke="#3d9bff" stroke-width="2.5" stroke-linecap="round"><path d="M17 33l-2 7M25 33l-2 7M33 33l-2 7"/></g>',
    snow: '<path d="M12 28h24a8 8 0 0 0 0-16 10 10 0 0 0-19 2 7 7 0 0 0-5 14z" fill="#cfe6f2"/><g fill="#ffffff"><circle cx="17" cy="36" r="2"/><circle cx="25" cy="39" r="2"/><circle cx="33" cy="36" r="2"/></g>',
    storm: '<path d="M12 28h24a8 8 0 0 0 0-16 10 10 0 0 0-19 2 7 7 0 0 0-5 14z" fill="#7fa3b8"/><path d="M25 29l-5 8h5l-3 7 8-10h-5l3-5z" fill="#ffc53d"/>',
  };
  const icon = (k) => `<svg viewBox="0 0 48 48">${ICONS[k] || ICONS.cloudy}</svg>`;
  const row = (label, value) => `<div><span class="dim">${label}</span><span class="v">${value}</span></div>`;

  const RENDER = {
    forecast(p) {
      const d = p.data, c = d.current;
      return `<div class="fc-now">${icon(c.icon).replace("<svg", '<svg style="width:84px;height:84px"')}
        <div class="t">${c.temp}°</div><div class="d">${fmt.esc(c.desc)}<br>Percepita ${c.feels}° · Umidità ${c.humidity}%<br>Vento ${c.wind} km/h</div></div>
        <div class="fc-days">${d.days.map((x, i) => `<div class="fc-day ${i === 0 ? "today" : ""}" style="animation-delay:${i * 70}ms">
          <div class="n">${fmt.esc(x.label)}</div><div class="dt">${fmt.esc(x.date)}</div>${icon(x.icon)}
          <div><span class="mx">${x.tmax}°</span> <span class="mn">${x.tmin}°</span></div>
          <div class="rn">☂ ${x.rain ?? 0}% · ${x.wind} km/h</div><div class="ds">${fmt.esc(x.desc)}</div></div>`).join("")}</div>`;
    },
    text: (p) => `<div class="p-text">${fmt.esc(p.body)}</div>`,
    list: (p) => `<div class="p-list">${p.items.map((it) => `<div>${it.status ? `<i class="dot ${it.status}"></i>` : '<i class="bullet"></i>'}<span>${fmt.esc(it.label)}</span>${it.value ? `<span class="v">${fmt.esc(it.value)}</span>` : ""}</div>`).join("")}</div>`,
    stats: (p) => `<div class="p-stats">${p.items.map((it) => `<div><div class="row"><span>${fmt.esc(it.label)}</span><b class="mono">${fmt.esc(it.value)}</b></div><div class="bar ${it.percent > 90 ? "down" : it.percent > 75 ? "warn" : ""}"><i style="width:${it.percent}%"></i></div></div>`).join("")}</div>`,
    image: (p) => `<figure class="p-image"><img src="${fmt.esc(p.src)}?t=${Date.now()}" alt="${fmt.esc(p.caption || p.title || "")}">
      ${p.caption || p.credit ? `<figcaption>${p.caption ? `<span>${fmt.esc(p.caption)}</span>` : ""}${p.credit ? `<small>${p.page ? `<a href="${fmt.esc(p.page)}" target="_blank" rel="noopener">${fmt.esc(p.credit)}</a>` : fmt.esc(p.credit)}</small>` : ""}</figcaption>` : ""}</figure>`,
    steps: (p) => `<ol class="p-steps">${(p.items || []).map((s, i) => `<li style="animation-delay:${i * 70}ms"><span class="p-n">${i + 1}</span><span>${fmt.esc(s)}</span></li>`).join("")}</ol>`,
    table: (p) => `<div class="p-table"><table><thead><tr>${(p.columns || []).map((c) => `<th>${fmt.esc(c)}</th>`).join("")}</tr></thead><tbody>${(p.rows || []).map((r) => `<tr>${r.map((c, i) => `<td${i ? "" : ' class="first"'}>${fmt.esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`,
    quote: (p) => `<blockquote class="p-quote">${fmt.esc(p.body)}${p.source ? `<cite>— ${fmt.esc(p.source)}</cite>` : ""}</blockquote>`,
    route(p) {
      const d = p.data || {};
      const traffic = d.delay != null ? (d.delay >= 3 ? `<span style="color:#ffb547">+${d.delay} min di traffico</span>` : '<span style="color:#3ddc97">traffico scorrevole</span>') : '<span class="dim">stima senza traffico</span>';
      return `<div class="p-list"><div><span class="dim">Tempo ${fmt.esc(d.mode || "")}</span><span class="v" style="font-size:22px;color:var(--cyan)">${fmt.esc(d.duration)}</span></div>
        ${row("Traffico", traffic)}
        ${row("Distanza", fmt.esc(d.distance))}
        ${d.via ? row("Via", fmt.esc(d.via)) : ""}
        ${d.leave_by ? row("Parti entro", fmt.esc(d.leave_by)) : ""}
        ${row("Arrivo", fmt.esc(d.arrive_at))}</div>`;
    },
    routemap(p) {
      const d = p.data || {};
      const traffic = d.delay != null ? (d.delay >= 3 ? `<span class="rm-bad">+${d.delay} min di traffico</span>` : '<span class="rm-ok">traffico scorrevole</span>') : '<span class="dim">stima senza traffico</span>';
      const steps = (d.steps || []).map((s, i) => `<li><span class="rm-n">${i + 1}</span>${fmt.esc(s)}</li>`).join("");
      return `<div class="rm-wrap"><div class="rm-map" data-route></div>
        <div class="rm-side">
          <div class="rm-dest">${fmt.esc(d.to || "")}</div>
          ${d.to_detail ? `<div class="rm-from dim">${fmt.esc(d.to_detail)}</div>` : ""}
          <div class="rm-from dim">da ${fmt.esc(d.from || "")} · ${fmt.esc(d.mode || "")}</div>
          <div class="rm-time">${fmt.esc(d.duration || "")}</div>
          <div class="rm-traffic">${traffic}</div>
          <div class="rm-grid">
            <div><small>Distanza</small><b>${fmt.esc(d.distance || "")}</b></div>
            <div><small>${d.leave_by ? "Appuntamento" : "Arrivo"}</small><b>${fmt.esc(d.arrive_at || "")}</b></div>
            ${d.leave_by ? `<div><small>Parti entro</small><b>${fmt.esc(d.leave_by)}</b></div>` : ""}
            ${d.via ? `<div class="rm-via"><small>Via</small><b>${fmt.esc(d.via)}</b></div>` : ""}
          </div>
          ${steps ? `<div class="rm-steps-title dim">Indicazioni</div><ol class="rm-steps">${steps}</ol>` : ""}
        </div></div>`;
    },
    code: (p) => `<div class="p-code"><div class="p-code-head"><span class="p-code-lang">${fmt.esc(p.language || "testo")}</span>
      <span class="dim">${String(p.content || "").split("\n").length} righe</span><button class="p-code-copy" type="button">Copia</button></div>
      <pre><code>${fmt.esc(p.content || "")}</code></pre></div>`,
    kv: (p) => `<div class="p-list">${Object.entries(p.data || {}).map(([k, v]) => row(fmt.esc(k), fmt.esc(v))).join("")}</div>`,
  };
  const WIDE = { forecast: 1, text: 1, routemap: 1 };
  let leaflet = null;
  const loadLeaflet = () => leaflet || (leaflet = new Promise((ok, ko) => {
    const v = window.JARVIS_ASSET_V ? `?v=${window.JARVIS_ASSET_V}` : "";
    const css = document.createElement("link"); css.rel = "stylesheet"; css.href = `/vendor/leaflet.css${v}`; document.head.appendChild(css);
    const s = document.createElement("script"); s.src = `/vendor/leaflet.js${v}`; s.onload = () => ok(window.L); s.onerror = ko; document.head.appendChild(s);
  }));
  const copyText = (text, button) => {
    const done = () => { button.textContent = "Copiato"; setTimeout(() => { button.textContent = "Copia"; }, 1500); };
    if (navigator.clipboard && window.isSecureContext) { navigator.clipboard.writeText(text).then(done).catch(() => {}); return; }
    const area = document.createElement("textarea");
    area.value = text; area.style.position = "fixed"; area.style.opacity = "0";
    document.body.appendChild(area); area.select();
    try { document.execCommand("copy"); done(); } catch (err) { console.warn(err); }
    area.remove();
  };
  const AFTER = {
    code(el, p) {
      const b = el.querySelector(".p-code-copy");
      if (b) b.addEventListener("click", (e) => { e.stopPropagation(); copyText(p.content || "", b); });
    },
    async routemap(el, p) {
      const d = p.data || {}, box = el.querySelector("[data-route]");
      if (!box || !(d.path && d.path.length || d.a)) { if (box) box.classList.add("rm-none"); return; }
      try {
        const L = await loadLeaflet();
        const map = L.map(box, { zoomControl: false, attributionControl: true, fadeAnimation: false });
        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",
          { maxZoom: 19, className: "rm-tiles", attribution: "© OpenStreetMap" }).addTo(map);
        const pts = d.path && d.path.length ? d.path : [d.a, d.b].filter(Boolean);
        L.polyline(pts, { color: "#000", weight: 9, opacity: 0.45 }).addTo(map);
        const line = L.polyline(pts, { color: d.delay >= 3 ? "#ffb547" : "#29e0ff", weight: 5, opacity: 0.95 }).addTo(map);
        const dot = (ll, color) => L.circleMarker(ll, { radius: 8, color: "#fff", weight: 2, fillColor: color, fillOpacity: 1 }).addTo(map);
        if (d.a) dot(d.a, "#3ddc97");
        if (d.b) dot(d.b, "#ff4d6a");
        map.fitBounds(line.getBounds(), { padding: [36, 36] });
        setTimeout(() => map.invalidateSize(), 400);
      } catch (err) { box.classList.add("rm-none"); }
    },
  };
  D.stagePanels = { render: RENDER, wide: WIDE };

  const spanOf = (p) => Math.max(1, Math.min(12, parseInt(p.span, 10) || 12));

  D.renderStage = (ui) => {
    $("stage-title").textContent = ui.title || "";
    $("stage-sub").textContent = ui.subtitle || "";
    const grid = ui.layout === "grid";
    $("stage-body").classList.toggle("grid12", grid);
    $("stage-body").innerHTML = (ui.panels || []).map((p, i) => `<div class="panel ${!grid && WIDE[p.type] ? "wide" : ""}" style="animation-delay:${i * 90}ms${grid ? `;--span:${spanOf(p)}` : ""}">
      ${p.title ? `<h3 class="panel-title">${fmt.esc(p.title)}</h3>` : ""}${(RENDER[p.type] || RENDER.text)(p)}</div>`).join("");
    [...$("stage-body").children].forEach((el, i) => { const p = (ui.panels || [])[i]; if (p && AFTER[p.type]) AFTER[p.type](el, p); });
  };

  D.renderSkeleton = (sk) => {
    $("stage-body").classList.remove("grid12");
    $("stage-title").textContent = "Elaborazione…"; $("stage-sub").textContent = "Preparo le informazioni";
    $("stage-body").innerHTML = sk.panels.map((p) => `<div class="panel ${WIDE[p.type] ? "wide" : ""}"><h3 class="panel-title">${fmt.esc(p.title)}</h3><div class="skeleton"></div></div>`).join("");
  };
})();
