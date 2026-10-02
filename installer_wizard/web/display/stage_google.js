(() => {
  const D = window.JarvisDisplay, { fmt } = D;
  const { render, wide } = D.stagePanels;
  const esc = fmt.esc;
  const PALETTE = ["#29e0ff", "#b36bff", "#3dffa8", "#ffb547", "#ff6bb5", "#3d7bff", "#ffd84d"];
  const DRIVE = { doc: "📄", sheet: "📊", slides: "📽", pdf: "📕", folder: "📁", image: "🖼", video: "🎬", audio: "🎵", form: "📝", file: "📎" };

  const hue = (text) => PALETTE[[...String(text)].reduce((a, c) => a + c.charCodeAt(0), 0) % PALETTE.length];
  const initials = (name) => String(name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("") || "?";
  const avatar = (name) => `<span class="g-av" style="--c:${hue(name)}">${esc(initials(name))}</span>`;
  const delay = (i) => `style="animation-delay:${i * 70}ms"`;

  function ring(done, total) {
    const pct = total ? done / total : 1, r = 34, c = 2 * Math.PI * r;
    return `<svg class="g-ring" viewBox="0 0 84 84"><circle cx="42" cy="42" r="${r}" class="bg"/>
      <circle cx="42" cy="42" r="${r}" class="fg" stroke-dasharray="${c}" stroke-dashoffset="${c * (1 - pct)}"/>
      <text x="42" y="47">${total}</text></svg>`;
  }

  render.gcal = (p) => {
    const d = p.data || {}, events = d.events || [];
    if (!events.length) return '<div class="g-empty">Nessun impegno</div>';
    const now = Date.now() / 1000;
    const next = events.find((e) => e.ts > now);
    let day = "";
    return `<div class="g-timeline">${events.map((e, i) => {
      const head = e.day !== day ? `<div class="g-dayhead">${esc(e.day)}</div>` : "";
      day = e.day;
      const cls = e.ts < now && !e.all_day ? "past" : e === next ? "next" : "";
      const left = e === next ? Math.round((e.ts - now) / 60) : null;
      return `${head}<div class="g-ev ${cls}" ${delay(i)} style="--c:${hue(e.calendar || e.title)}">
        <div class="g-time">${e.all_day ? "tutto il giorno" : `${esc(e.start)}${e.end ? `<small>${esc(e.end)}</small>` : ""}`}</div>
        <div class="g-bar"></div>
        <div class="g-info"><b>${esc(e.title)}</b>${e.where ? `<span>📍 ${esc(e.where)}</span>` : ""}${e.calendar ? `<span class="g-tag">${esc(e.calendar)}</span>` : ""}
        ${left != null && left < 24 * 60 ? `<em>tra ${left < 60 ? `${left} min` : `${Math.floor(left / 60)} h ${left % 60} min`}</em>` : ""}</div></div>`;
    }).join("")}</div>`;
  };

  render.gfree = (p) => {
    const d = p.data || {}, span = d.to - d.from;
    const pos = (h) => `${((Math.max(d.from, Math.min(d.to, h)) - d.from) / span) * 100}%`;
    const width = (a, b) => `${((Math.min(d.to, b) - Math.max(d.from, a)) / span) * 100}%`;
    const hours = Array.from({ length: span + 1 }, (_, i) => d.from + i);
    const label = (h) => `${String(Math.floor(h)).padStart(2, "0")}:${String(Math.round((h % 1) * 60)).padStart(2, "0")}`;
    return `<div class="g-free"><div class="g-track">
      ${(d.slots || []).map(([a, b], i) => `<i class="free" ${delay(i)} style="left:${pos(a)};width:${width(a, b)}"></i>`).join("")}
      ${(d.busy || []).map((e, i) => `<i class="busy" ${delay(i)} style="left:${pos(e.start)};width:${width(e.start, e.end)}" title="${esc(e.title)}"><span>${esc(e.title)}</span></i>`).join("")}
      </div><div class="g-hours">${hours.map((h) => `<span style="left:${pos(h)}">${h}</span>`).join("")}</div>
      <div class="g-slots">${(d.slots || []).map(([a, b]) => `<span>🟢 ${label(a)} – ${label(b)}</span>`).join("")}</div></div>`;
  };

  render.gmail = (p) => {
    const d = p.data || {};
    if (!(d.items || []).length) return '<div class="g-empty">📭 Casella in ordine</div>';
    return `<div class="g-mails"><div class="g-count"><b>${d.total}</b><span>non lett${d.total === 1 ? "a" : "e"}</span></div>
      ${d.items.map((m, i) => `<div class="g-mail" ${delay(i)}>${avatar(m.from)}<div class="g-mbody">
        <div class="g-mtop"><b>${esc(m.from)}</b><small>${esc(m.when)}</small></div>
        <div class="g-subj">${esc(m.subject)}</div><div class="g-snip">${esc(m.snippet)}</div></div></div>`).join("")}</div>`;
  };

  render.gmailread = (p) => {
    const m = p.data || {};
    return `<div class="g-letter">${avatar(m.from)}<div><div class="g-mtop"><b>${esc(m.from)}</b><small>${esc(m.when)}</small></div>
      <div class="g-subj big">${esc(m.subject)}</div></div></div><div class="g-letter-body">${esc(m.body)}</div>`;
  };

  render.gtasks = (p) => {
    const d = p.data || {}, items = d.items || [];
    const late = items.filter((t) => t.late).length;
    return `<div class="g-tasks"><div class="g-thead">${ring(items.length - late, items.length)}
        <div><b>${items.length ? `${items.length} da fare` : "Tutto fatto!"}</b>${late ? `<span class="late">${late} in ritardo</span>` : ""}
        ${d.done ? `<span class="g-done">✓ ${esc(d.done)}</span>` : ""}</div></div>
      ${items.map((t, i) => `<div class="g-task ${t.late ? "late" : ""}" ${delay(i)}><i></i><div><b>${esc(t.title)}</b>
        ${t.notes ? `<small>${esc(t.notes)}</small>` : ""}</div>${t.due ? `<span>${esc(t.due)}</span>` : ""}</div>`).join("")}</div>`;
  };

  render.gnotes = (p) => `<div class="g-notes">${((p.data || {}).items || []).map((n, i) => `<div class="g-note" ${delay(i)}
      style="--c:${hue(n.title || n.text)};--r:${((i * 37) % 7) - 3}deg">${n.title ? `<b>${esc(n.title)}</b>` : ""}<p>${esc(n.text)}</p></div>`).join("")}</div>`;

  render.gcontact = (p) => {
    const c = p.data || {};
    return `<div class="g-contact">${avatar(c.name).replace("g-av", "g-av xl")}<h4>${esc(c.name)}</h4>
      ${(c.phones || []).map((x) => `<div class="g-ci">📞 <span>${esc(x)}</span></div>`).join("")}
      ${(c.emails || []).map((x) => `<div class="g-ci">✉️ <span>${esc(x)}</span></div>`).join("")}</div>`;
  };

  render.gdrive = (p) => `<div class="g-drive">${((p.data || {}).files || []).map((f, i) => `<div class="g-file" ${delay(i)}>
      <span class="g-fi">${DRIVE[f.kind] || DRIVE.file}</span><b>${esc(f.name)}</b><small>${esc(f.modified)}</small></div>`).join("")}</div>`;

  Object.assign(wide, { gcal: 1, gfree: 1, gmail: 1, gmailread: 1, gtasks: 1, gnotes: 1, gdrive: 1 });
})();
