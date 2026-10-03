(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  let brainData = null;

  const ICON = { cloud: "☁", server: "🖧", local: "🖥" };
  const originBadge = (e) => e.origin === "local" ? '<span class="badge br-local">🖥 locale</span>'
    : `<span class="badge br-${e.origin}">${ICON[e.origin]} ${fmt.esc(e.provider)}</span>`;
  const seconds = (ms) => `${(ms / 1000).toFixed(1).replace(".", ",")} s`;

  async function loadModels() {
    try {
      const d = await A.api("GET", "/api/models");
      $("models-body").innerHTML = d.models.map((m) => `<tr><td class="mono">${fmt.esc(m.name)}</td><td class="mono">${fmt.bytes(m.size)}</td>
        <td>${d.loaded.includes(m.name) ? '<span class="badge ok">in memoria</span>' : '<span class="badge">su disco</span>'}</td>
        <td style="text-align:right"><button class="btn sm danger" data-del="${fmt.esc(m.name)}">Elimina</button></td></tr>`).join("")
        || `<tr><td colspan="4" class="faint">Nessun modello locale: Jarvis può usare solo il cloud.</td></tr>`;
    } catch (e) { $("models-body").innerHTML = `<tr><td colspan="4" class="faint">${fmt.esc(e.message)}</td></tr>`; }
  }

  async function loadBrains() {
    try { brainData = await A.api("GET", "/api/brains"); } catch (e) { $("br-catalog").innerHTML = `<div class="faint">${fmt.esc(e.message)}</div>`; return; }
    renderBrains();
  }

  function nowCard(role) {
    const title = `${role.icon} ${role.label}`;
    if (!role.active) return `<div class="br-now-kind">${title}</div><div class="br-now-model warn">Nessun cervello disponibile</div>
      <div class="faint">Scarica un modello locale o collega un servizio cloud qui sotto.</div>`;
    const st = (role.entries.find((e) => e.name === role.active.ref) || {}).stats;
    return `<div class="br-now-kind">${title}</div><div class="br-now-model">${fmt.esc(role.active.model)}</div>
      <div class="br-now-meta">${originBadge(role.active)}${st ? ` <span class="faint">${st.ok} risposte · ~${seconds(st.avg_ms)}</span>` : ""}</div>`;
  }

  function autoNote(d, role) {
    if (role.id === "chat") return `Automatico: scelto da Jarvis in base all'hardware (veloce: ${fmt.esc(d.fast)}).`;
    if (role.id === "deep") return `Automatico: scelto da Jarvis in base all'hardware (potente: ${fmt.esc(d.main)}).`;
    return "Automatico: segue la lista Ragionamento.";
  }

  function priorityList(d, role, cat) {
    const activeRef = role.active && role.active.ref;
    const items = role.entries.map((m, i) => {
      const c = cat[m.name] || {}, st = m.stats;
      const status = m.origin === "server"
        ? (m.available ? '<span style="color:var(--green)">collegato</span>' : '<span style="color:var(--amber)">server rimosso — verrà saltato</span>')
        : m.origin === "cloud"
        ? (m.available ? '<span style="color:var(--green)">collegato</span>' : '<span style="color:var(--amber)">chiave mancante — verrà saltato</span>')
        : (m.available ? '<span style="color:var(--green)">scaricato</span>' : '<span style="color:var(--amber)">da scaricare — verrà saltato</span>');
      const sub = [m.name === activeRef ? '<b style="color:var(--cyan)">▶ in uso</b>' : "", `${ICON[m.origin]} ${fmt.esc(m.provider)}`, status,
        c.fit && c.fit.label, st ? `${st.ok} risposte · ~${seconds(st.avg_ms)}${st.fail ? ` · ${st.fail} errori` : ""}` : ""].filter(Boolean).join(" · ");
      return A.prioItem(m.name, i, c.label && c.label !== m.name ? `${c.label} · ${m.model}` : m.model, sub, !m.available, false);
    }).join("");
    return items + (role.custom ? "" : `<div class="muted-note" style="margin:4px 6px">${autoNote(d, role)}</div>`);
  }

  function rolePanel(role) {
    return `<div class="panel" data-role="${role.id}">
      <div class="panel-title">${role.icon} ${fmt.esc(role.label)}</div>
      <div class="muted-note">${fmt.esc(role.hint)}</div>
      <div class="prio" data-prio="${role.id}"></div>
      <div class="actions" style="margin-top:10px"><button class="btn sm" data-br-reset="${role.id}">Automatico</button></div>
    </div>`;
  }

  function mountRoles(host, roles) {
    host.innerHTML = roles.map(rolePanel).join("");
    host.querySelectorAll("[data-prio]").forEach((list) => A.makeSortable(list, (items) => saveBrains({ [list.dataset.prio]: items })));
  }

  function catalogItem(d, m) {
    const buttons = d.roles.map((r) => `<button class="btn sm" data-add="${r.id}" data-m="${fmt.esc(m.name)}" ${r.entries.some((e) => e.name === m.name) ? "disabled" : ""} title="Aggiungi a ${fmt.esc(r.label)}">+ ${r.icon}</button>`).join("");
    return `<div class="cat-item"><div>
        <div class="nm">${fmt.esc(m.label)} <span class="faint mono" style="font-size:11px">${fmt.esc(m.name)}${m.size_gb ? ` · ${m.size_gb} GB` : ""}</span>
          ${m.name === d.suggested.chat ? '<span class="badge ok">consigliato ⚡</span>' : ""}${m.name === d.suggested.deep ? '<span class="badge ok">consigliato 🧠</span>' : ""}</div>
        <div class="nt">${fmt.esc(m.notes || "")}</div>
        <div class="fit ${m.fit.level}">${fmt.esc(m.fit.label)}${m.installed ? " · ✓ scaricato" : ""}</div></div>
      <div class="actions" style="justify-content:flex-end">
        ${buttons}
        ${m.installed ? "" : `<button class="btn sm primary" data-dl="${fmt.esc(m.name)}" data-size="${m.size_gb || ""}">Scarica</button>`}</div></div>`;
  }

  function renderBrains() {
    const d = brainData, cat = Object.fromEntries(d.catalog.map((m) => [m.name, m]));
    $("br-routing").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.r === d.routing));
    $("br-now-grid").innerHTML = d.roles.map((r) => `<div class="br-now-card">${nowCard(r)}</div>`).join("");
    const l = d.last_used || {};
    $("br-last").innerHTML = l.model ? `Ultima risposta: <b>${fmt.esc(l.model)}</b> ${originBadge(l)} in ${seconds(l.ms)}` : "";
    const host = $("br-roles");
    if (host.children.length !== d.roles.length) mountRoles(host, d.roles);
    d.roles.forEach((r) => { host.querySelector(`[data-prio="${r.id}"]`).innerHTML = priorityList(d, r, cat); });
    const hw = d.hardware || {};
    $("br-hw").textContent = `${hw.ram_gb || "?"} GB RAM · ${hw.gpu ? `${hw.gpu} ${hw.vram_gb} GB` : "solo CPU"}`;
    $("br-catalog").innerHTML = d.catalog.map((m) => catalogItem(d, m)).join("");
  }

  async function saveBrains(body) {
    try { brainData = await A.api("PUT", "/api/brains", body); renderBrains(); } catch (e) { A.toast(e.message, true); loadBrains(); }
  }

  async function addTo(kind, name, first = false) {
    if (!brainData) await loadBrains();
    const role = brainData.roles.find((r) => r.id === kind);
    if (!role) return;
    const list = role.entries.map((x) => x.name);
    if (list.includes(name)) { A.toast("È già nella lista"); return; }
    await saveBrains({ [kind]: first ? [name, ...list] : [...list, name] });
    A.toast(`Aggiunto ${first ? "in cima" : "in coda"} a ${role.icon} ${role.label}: trascinalo per cambiarne la priorità`);
  }

  async function pullModel(name, size) {
    if (!confirm(`Scaricare ${name}${size ? ` (${size} GB)` : ""}? Il download continua in background.`)) return false;
    try { await A.api("POST", "/api/models/pull", { name }); A.toast(`Download di ${name} avviato`); return true; } catch (e) { A.toast(e.message, true); return false; }
  }

  function showSource(v) {
    $("br-source").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.v === v));
    ["local", "servers", "cloud"].forEach((x) => $(`br-view-${x}`).classList.toggle("on", x === v));
  }

  async function loadOllama() {
    try {
      const c = await A.api("GET", "/api/config");
      const item = (c.editable || []).find((x) => x.key === "JARVIS_OLLAMA_URL");
      $("ol-url").value = (item && item.value) || "";
    } catch (e) { }
  }

  async function testOllama() {
    $("ol-res").textContent = "Prova in corso…";
    try {
      const r = await A.api("POST", "/api/brains/ollama/test", { url: $("ol-url").value.trim() });
      $("ol-res").innerHTML = r.ok ? `✅ ${fmt.esc(r.url)} risponde: Ollama ${fmt.esc(r.version)}, ${r.models.length} modelli installati${r.models.length ? ` (${r.models.slice(0, 6).map(fmt.esc).join(", ")}${r.models.length > 6 ? "…" : ""})` : ""}`
        : `⚠ ${fmt.esc(r.url)}: ${fmt.esc(r.error)}`;
      return r.ok;
    } catch (e) { $("ol-res").textContent = `⚠ ${e.message}`; return false; }
  }

  function roleLabel(id) {
    const role = brainData && brainData.roles.find((r) => r.id === id);
    return role ? `${role.icon} ${role.label}` : id;
  }

  function init() {
    $("ol-test").addEventListener("click", testOllama);
    $("ol-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      if ($("ol-url").value.trim() && !(await testOllama()) && !confirm("Il server non risponde: salvare comunque?")) return;
      try {
        await A.api("PUT", "/api/config", { JARVIS_OLLAMA_URL: $("ol-url").value.trim() });
        A.toast($("ol-url").value.trim() ? "Server Ollama remoto salvato: i suoi modelli sono nel catalogo qui sotto, aggiungili con + ⚡ o + 🧠" : "Torno all'Ollama locale: riconfiguro i servizi");
        loadOllama(); loadModels(); loadBrains();
      } catch (err) { A.toast(err.message, true); }
    });
    $("models-body").addEventListener("click", async (e) => {
      const name = e.target.dataset.del; if (!name || !confirm(`Eliminare ${name}?`)) return;
      try { await A.api("DELETE", `/api/models/${encodeURIComponent(name)}`); A.toast("Modello eliminato"); loadModels(); } catch (err) { A.toast(err.message, true); }
    });
    $("pull-btn").addEventListener("click", async () => {
      const name = $("pull-name").value.trim(); if (!name) return;
      try { await A.api("POST", "/api/models/pull", { name }); A.toast(`Download di ${name} avviato`); } catch (e) { A.toast(e.message, true); }
    });
    $("br-routing").addEventListener("click", (e) => { const b = e.target.closest("[data-r]"); if (b) saveBrains({ routing: b.dataset.r }).then(() => A.toast("Instradamento aggiornato")); });
    $("br-roles").addEventListener("click", (e) => { const b = e.target.closest("[data-br-reset]"); if (b) saveBrains({ [b.dataset.brReset]: [] }).then(() => A.toast("Lista tornata automatica")); });
    $("br-source").addEventListener("click", (e) => { const b = e.target.closest("[data-v]"); if (b) showSource(b.dataset.v); });
    $("br-catalog").addEventListener("click", async (e) => {
      const add = e.target.closest("[data-add]"), dl = e.target.closest("[data-dl]");
      if (dl) return pullModel(dl.dataset.dl, dl.dataset.size);
      if (!add) return;
      const m = brainData.catalog.find((x) => x.name === add.dataset.m);
      await addTo(add.dataset.add, add.dataset.m);
      if (m && !m.installed) pullModel(m.name, m.size_gb);
    });
    $("br-test").addEventListener("submit", async (e) => {
      e.preventDefault(); const text = $("br-q").value.trim(); if (!text) return;
      try {
        const r = await A.api("POST", "/api/brains/test", { text });
        $("br-res").innerHTML = `${roleLabel(r.kind)} <span class="faint">— ${fmt.esc(r.reason)} · risponderà ${fmt.esc(r.models[0] || "nessuno")}${r.models.length > 1 ? `, poi in ordine: ${r.models.slice(1).map(fmt.esc).join(" → ")}` : ""}</span>`;
      } catch (err) { A.toast(err.message, true); }
    });
  }

  function onState(s) {
    const mp = s.model_pull;
    if (!mp) return;
    $("pull-status").textContent = `${mp.name}: ${mp.status}${mp.percent ? ` — ${mp.percent}%` : ""}`; $("pull-bar").style.width = `${mp.percent || 0}%`;
    const sig = `${mp.name}|${mp.status}`;
    if (sig !== window.__pullSig) { window.__pullSig = sig; if (A.isOn("models") && /completato|errore/.test(mp.status)) { loadModels(); loadBrains(); } }
  }

  A.brain = { reload: loadBrains, addTo, lists: () => brainData, showSource };
  A.tab("models", { title: "Cervello", init() { init(); if (A.brainCloud) A.brainCloud.init(); if (A.brainServers) A.brainServers.init(); if (A.brainAssign) A.brainAssign.init(); }, async load() { loadModels(); loadOllama(); await loadBrains(); if (A.brainCloud) A.brainCloud.load(); if (A.brainServers) A.brainServers.load(); if (A.brainAssign) A.brainAssign.load(); }, onState });
})();
