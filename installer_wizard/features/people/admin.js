(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  const DAYS = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"];
  const REMINDER_ICON = { compleanno: "🎂", onomastico: "🌼", evento: "📅", scadenza: "⚠️" };
  const initials = (n) => (n || "?").split(/\s+/).map((x) => x[0]).join("").slice(0, 2).toUpperCase();
  const avatar = (p, size = 48) => `<img class="avatar" style="width:${size}px;height:${size}px" src="/api/vision/people/${encodeURIComponent(p.slug)}/photo.jpg" onerror="this.outerHTML='<div class=&quot;avatar&quot; style=&quot;width:${size}px;height:${size}px&quot;>${fmt.esc(initials(p.name))}</div>'">`;
  const ago = (t) => t ? `${fmt.duration(Date.now() / 1000 - t)} fa` : "mai";
  let peopleData = { people: [], roles: {} }, peopleSchema = null, currentPerson = null, currentSection = "identity";
  let personCache = null, peopleFilter = "";
  const saveTimers = {};

  async function loadPeople() {
    try {
      if (!peopleSchema) peopleSchema = await A.api("GET", "/api/people/schema");
      peopleData = await A.api("GET", "/api/people");
      const rem = await A.api("GET", "/api/people/reminders?days=45");
      $("reminders").innerHTML = rem.reminders.length ? rem.reminders.map((r) => `<div class="rem" data-slug="${fmt.esc(r.slug)}">
          <span class="ic">${REMINDER_ICON[r.type] || "•"}</span><span>${fmt.esc(r.title)}</span>
          <span class="when">${r.days === 0 ? "oggi" : r.days === 1 ? "domani" : `tra ${r.days} giorni`}</span></div>`).join("")
        : '<div class="faint">Nessuna ricorrenza nei prossimi 45 giorni.</div>';
    } catch (e) { A.toast(e.message, true); return; }
    renderPeopleList();
    if (currentPerson && !$("person-detail").contains(document.activeElement)) openPerson(currentPerson);
  }

  function renderPeopleList() {
    const s = A.state;
    const present = new Set(((s && s.presence && s.presence.people) || []).filter((p) => p.known).map((p) => p.slug));
    const q = peopleFilter.toLowerCase();
    const list = peopleData.people.filter((p) => !q || JSON.stringify([p.name, p.nickname, p.tags, p.occupation]).toLowerCase().includes(q));
    $("people-list").innerHTML = list.map((p) => `<div class="person ${p.slug === currentPerson ? "on" : ""}" data-slug="${fmt.esc(p.slug)}">
      ${avatar(p)}<div><div class="n">${fmt.esc(p.name)} ${present.has(p.slug) ? '<span class="present">● presente</span>' : ""}</div>
      <div class="m">${fmt.esc(peopleData.roles[p.role] || p.role || "")}${p.computed && p.computed.age != null ? ` · ${p.computed.age} anni` : ""} · visto ${ago(p.stats && p.stats.last_seen)}</div></div></div>`).join("")
      || '<div class="faint">Nessuna persona trovata.</div>';
  }

  function fieldInput(f, value, path) {
    const v = value ?? "";
    const attrs = `data-path="${fmt.esc(path)}" data-type="${f.type}"`;
    switch (f.type) {
      case "textarea": return `<textarea ${attrs} rows="3" placeholder="${fmt.esc(f.placeholder || "")}">${fmt.esc(v)}</textarea>`;
      case "bool": return `<label class="row" style="margin:0;gap:8px"><input type="checkbox" ${attrs} style="width:auto" ${v ? "checked" : ""}> ${fmt.esc(f.label)}</label>`;
      case "select": return `<select ${attrs}>${(f.options || []).map((o) => `<option value="${fmt.esc(o)}" ${o === v ? "selected" : ""}>${fmt.esc((f.labels && f.labels[o]) || o || "—")}</option>`).join("")}</select>`;
      case "tags": return `<input ${attrs} value="${fmt.esc(Array.isArray(v) ? v.join(", ") : v)}" placeholder="separati da virgola">`;
      case "person": return `<select ${attrs}><option value="">—</option>${peopleData.people.filter((p) => p.slug !== currentPerson).map((p) => `<option value="${fmt.esc(p.slug)}" ${p.slug === v ? "selected" : ""}>${fmt.esc(p.name)}</option>`).join("")}</select>`;
      default: return `<input ${attrs} type="${{ date: "date", number: "number", email: "email", tel: "tel", url: "url" }[f.type] || "text"}" value="${fmt.esc(v)}" placeholder="${fmt.esc(f.placeholder || "")}">`;
    }
  }

  function listRow(f, row, i) {
    return `<div class="list-row" data-row="${i}">${f.fields.map((sf) => sf.type === "bool"
      ? `<div>${fieldInput(sf, row[sf.key], `${f.key}.${i}.${sf.key}`)}</div>`
      : `<div><label>${fmt.esc(sf.label)}</label>${fieldInput(sf, row[sf.key], `${f.key}.${i}.${sf.key}`)}</div>`).join("")}
      <button class="btn sm danger" data-del="${f.key}" data-idx="${i}" title="Rimuovi">✕</button></div>`;
  }

  function renderField(f, p) {
    if (f.type === "list") {
      const rows = p[f.key] || [];
      return `<div class="list-field wide" data-list="${f.key}"><label>${fmt.esc(f.label)}</label>
        ${rows.map((row, i) => listRow(f, row, i)).join("")}
        <button class="btn sm" data-add="${f.key}">+ Aggiungi</button></div>`;
    }
    const extra = f.key === "name_day" && p.computed && p.computed.name_day_auto ? ` <span class="faint">(automatico: ${p.computed.name_day})</span>` : "";
    return f.type === "bool" ? `<div>${fieldInput(f, p[f.key], f.key)}</div>`
      : `<div class="${f.type === "textarea" ? "wide" : ""}"><label>${fmt.esc(f.label)}${extra}</label>${fieldInput(f, p[f.key], f.key)}</div>`;
  }

  function voiceSection(p) {
    const vp = p.voiceprint || {};
    const vs = vp.enrolled ? `✓ registrata (${vp.samples} campioni${vp.updated ? `, ultimo ${new Date(vp.updated * 1000).toLocaleDateString("it-IT")}` : ""})`
      : vp.samples ? `in corso: ${vp.samples} campioni raccolti` : "non ancora registrata — dille «impara la mia voce» davanti alla webcam";
    return `<div class="form-grid">
        <div><label>Voce di Jarvis per questa persona</label><select data-voice="tts_voice"><option value="">Predefinita di sistema</option>
          ${Object.entries(peopleSchema.voices || {}).map(([v, label]) => `<option value="${v}" ${p.voice && p.voice.tts_voice === v ? "selected" : ""}>${fmt.esc(label)}</option>`).join("")}</select></div>
        <div><label>Velocità (${(p.voice && p.voice.speed) || 1.0})</label><input data-voice="speed" type="range" min="0.7" max="1.4" step="0.05" value="${(p.voice && p.voice.speed) || 1}"></div>
        <div><label>Tono (${(p.voice && p.voice.pitch) || 0})</label><input data-voice="pitch" type="range" min="-6" max="6" step="0.5" value="${(p.voice && p.voice.pitch) || 0}"></div>
        <div><label>Volume (${(p.voice && p.voice.volume) || 1.0})</label><input data-voice="volume" type="range" min="0.5" max="1.8" step="0.05" value="${(p.voice && p.voice.volume) || 1}"></div></div>
        <div class="row" style="justify-content:space-between; align-items:center; margin-top:6px">
          <div class="muted-note">Impronta vocale: ${vs}.</div>
          ${vp.enrolled || vp.samples ? '<button class="btn sm danger" id="forget-voice">Cancella impronta vocale</button>' : ""}</div>
        <div class="panel-title" style="margin-top:22px">Volto</div>
        <div class="actions"><button class="btn primary" id="enroll">📷 Registra / migliora il volto</button></div>
        <div class="muted-note">Mettiti davanti alla webcam a circa un metro e resta fermo 4 secondi. Ripeti con luci diverse per migliorare il riconoscimento.</div>`;
  }

  function habitsSection(p) {
    const h = p.habits, maxH = Math.max(1, ...h.arrival_hours), maxD = Math.max(1, ...h.weekdays);
    return `<div style="font-size:14px; margin-bottom:14px">${fmt.esc(h.summary)}</div>
        <div class="grid g2"><div><label>Orari di arrivo</label><div class="chart">${h.arrival_hours.map((v) => `<i style="height:${(v / maxH) * 100}%" title="${v}"></i>`).join("")}</div><div class="chart-lbl"><span>0</span><span>6</span><span>12</span><span>18</span><span>23</span></div></div>
        <div><label>Giorni della settimana</label><div class="chart">${h.weekdays.map((v) => `<i style="height:${(v / maxD) * 100}%" title="${v}"></i>`).join("")}</div><div class="chart-lbl">${DAYS.map((d) => `<span>${d}</span>`).join("")}</div></div></div>
        <div class="muted-note">${p.stats.visits} visite · ${fmt.duration(p.stats.total_seconds)} di presenza · prima volta ${p.stats.first_seen ? new Date(p.stats.first_seen * 1000).toLocaleDateString("it-IT") : "—"}</div>`;
  }

  function sectionHtml(p) {
    if (currentSection === "voice") return voiceSection(p);
    if (currentSection === "habits") return habitsSection(p);
    const sec = peopleSchema.sections.find((s) => s.id === currentSection);
    return `${sec.private ? '<div class="muted-note" style="margin:0 0 14px">🔒 Dati riservati: restano solo su questo dispositivo.</div>' : ""}
      <div class="form-grid">${sec.fields.map((f) => renderField(f, p)).join("")}</div>`;
  }

  async function openPerson(slug) {
    currentPerson = slug; renderPeopleList();
    try { personCache = await A.api("GET", `/api/people/${encodeURIComponent(slug)}`); } catch (e) { A.toast(e.message, true); return; }
    renderPerson();
  }

  function renderPerson() {
    const p = personCache, c = p.computed || {};
    const tabs = [...peopleSchema.sections.map((s) => [s.id, `${s.icon} ${s.title}`]), ["voice", "🎙 Voce e volto"], ["habits", "📈 Abitudini"]];
    $("person-detail").innerHTML = `
      <div class="row" style="gap:16px; margin-bottom:16px">${avatar(p, 72)}
        <div style="flex:1"><h2 style="margin:0; font-weight:400">${fmt.esc(c.display_name || p.name)}${p.nickname ? ` <span class="faint" style="font-size:15px">«${fmt.esc(p.nickname)}»</span>` : ""}</h2>
        <div class="faint" style="font-size:12px">${fmt.esc(peopleData.roles[p.role] || "")}${c.age != null ? ` · ${c.age} anni` : ""}${c.name_day ? ` · onomastico ${c.name_day.replace("-", "/")}` : ""}${p.occupation ? ` · ${fmt.esc(p.occupation)}` : ""}</div></div>
        <span class="saved" id="saved">✓ salvato</span>
        <button class="btn sm danger" id="forget" title="Elimina persona e tutti i suoi dati">Elimina</button></div>
      <div class="subtabs">${tabs.map(([id, t]) => `<button class="${id === currentSection ? "on" : ""}" data-sec="${id}">${t}</button>`).join("")}</div>
      <div id="section-body">${sectionHtml(p)}</div>`;
  }

  function autosave(key, value, delay = 600) {
    clearTimeout(saveTimers[key]);
    saveTimers[key] = setTimeout(async () => {
      try { await A.api("PUT", `/api/people/${encodeURIComponent(currentPerson)}`, { [key]: value }); personCache[key] = value; A.flash("saved");
        if (["first_name", "last_name", "role", "birthday", "nickname"].includes(key)) loadPeople(); }
      catch (e) { A.toast(e.message, true); }
    }, delay);
  }

  function readInput(el) {
    if (el.dataset.type === "bool") return el.checked;
    if (el.dataset.type === "tags") return el.value.split(",").map((x) => x.trim()).filter(Boolean);
    if (el.dataset.type === "number") return el.value === "" ? "" : Number(el.value);
    return el.value;
  }

  function collectList(key) {
    return [...document.querySelectorAll(`[data-list="${key}"] .list-row`)].map((row) => {
      const obj = {};
      row.querySelectorAll("[data-path]").forEach((el) => { obj[el.dataset.path.split(".")[2]] = readInput(el); });
      return obj;
    });
  }

  function onFieldChange(el) {
    const path = el.dataset.path; if (!path) return;
    const parts = path.split(".");
    if (parts.length === 3) autosave(parts[0], collectList(parts[0]));
    else autosave(path, readInput(el), el.dataset.type === "bool" || el.tagName === "SELECT" ? 0 : 600);
  }

  async function onDetailClick(e) {
    const t = e.target;
    if (t.dataset.sec) { currentSection = t.dataset.sec; renderPerson(); return; }
    if (t.dataset.add) {
      const key = t.dataset.add, f = peopleSchema.sections.flatMap((s) => s.fields).find((x) => x.key === key);
      personCache[key] = [...collectList(key), {}];
      t.closest(".list-field").outerHTML = renderField(f, personCache);
      return;
    }
    if (t.dataset.del) { const key = t.dataset.del; t.closest(".list-row").remove(); autosave(key, collectList(key), 0); return; }
    if (t.id === "enroll") {
      t.disabled = true; t.textContent = "Guarda la webcam… 4 secondi";
      try { const r = await A.api("POST", "/api/vision/people", { name: personCache.name }); A.toast(`Volto registrato: ${r.samples} campioni`); loadPeople(); }
      catch (err) { A.toast(err.message, true); }
      finally { t.disabled = false; t.textContent = "📷 Registra / migliora il volto"; }
    }
    if (t.id === "forget") {
      if (!confirm("Eliminare definitivamente questa persona con volto, dati, relazioni e abitudini?")) return;
      try { await A.api("DELETE", `/api/people/${encodeURIComponent(currentPerson)}`); currentPerson = null; $("person-detail").innerHTML = '<div class="faint">Persona eliminata.</div>'; loadPeople(); }
      catch (err) { A.toast(err.message, true); }
    }
    if (t.id === "forget-voice") {
      if (!confirm("Cancellare l'impronta vocale di questa persona?")) return;
      try { await A.api("DELETE", `/api/people/${encodeURIComponent(currentPerson)}/voiceprint`); A.toast("Impronta vocale cancellata"); openPerson(currentPerson); }
      catch (err) { A.toast(err.message, true); }
    }
  }

  function init() {
    $("people-list").addEventListener("click", (e) => { const el = e.target.closest(".person"); if (el) openPerson(el.dataset.slug); });
    $("reminders").addEventListener("click", (e) => { const el = e.target.closest(".rem"); if (el) openPerson(el.dataset.slug); });
    $("people-search").addEventListener("input", (e) => { peopleFilter = e.target.value; renderPeopleList(); });
    $("person-new").addEventListener("submit", async (e) => {
      e.preventDefault(); const name = $("person-new-name").value.trim(); if (!name) return;
      try { const p = await A.api("POST", "/api/people", { name }); $("person-new-name").value = ""; currentPerson = p.slug; await loadPeople(); openPerson(p.slug); }
      catch (err) { A.toast(err.message, true); }
    });
    $("person-detail").addEventListener("input", (e) => {
      if (e.target.dataset.voice) {
        const t = e.target; autosave("voice", { ...(personCache.voice || {}), [t.dataset.voice]: t.type === "range" ? parseFloat(t.value) : t.value });
      } else if (e.target.dataset.path && e.target.type !== "checkbox" && e.target.tagName !== "SELECT") onFieldChange(e.target);
    });
    $("person-detail").addEventListener("change", (e) => { if (e.target.type === "checkbox" || e.target.tagName === "SELECT") onFieldChange(e.target); });
    $("person-detail").addEventListener("click", onDetailClick);
  }

  function onState(s) {
    if (!A.isOn("people")) return;
    const pr = s.presence || {};
    $("presence-line").textContent = pr.status === "ok" ? (pr.summary || "") : (pr.error || "Webcam non disponibile");
    const sig = JSON.stringify((pr.people || []).map((x) => x.slug));
    if (sig !== window.__presenceSig) { window.__presenceSig = sig; renderPeopleList(); }
  }

  A.tab("people", {
    title: "Persone", init, onState,
    load() { $("cam").src = `/api/vision/stream.mjpg?t=${Date.now()}`; loadPeople(); },
    leave() { $("cam").removeAttribute("src"); },
  });
})();
