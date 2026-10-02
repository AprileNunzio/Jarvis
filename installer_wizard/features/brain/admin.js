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

  function nowCard(kind, active, entries) {
    const title = kind === "chat" ? "⚡ Conversazione" : "🧠 Ragionamento";
    if (!active) return `<div class="br-now-kind">${title}</div><div class="br-now-model warn">Nessun cervello disponibile</div>
      <div class="faint">Scarica un modello locale o collega un servizio cloud qui sotto.</div>`;
    const st = (entries.find((e) => e.name === active.ref) || {}).stats;
    return `<div class="br-now-kind">${title}</div><div class="br-now-model">${fmt.esc(active.model)}</div>
      <div class="br-now-meta">${originBadge(active)}${st ? ` <span class="faint">${st.ok} risposte · ~${seconds(st.avg_ms)}</span>` : ""}</div>`;
  }

  function priorityList(d, kind, cat) {
    const activeRef = d.active[kind] && d.active[kind].ref;
    return d[kind].map((m, i) => {
      const c = cat[m.name] || {}, st = m.stats;
      const status = m.origin === "server"
        ? (m.available ? '<span style="color:var(--green)">collegato</span>' : '<span style="color:var(--amber)">server rimosso — verrà saltato</span>')
        : m.origin === "cloud"
        ? (m.available ? '<span style="color:var(--green)">collegato</span>' : '<span style="color:var(--amber)">chiave mancante — verrà saltato</span>')
        : (m.available ? '<span style="color:var(--green)">scaricato</span>' : '<span style="color:var(--amber)">da scaricare — verrà saltato</span>');
      const sub = [m.name === activeRef ? '<b style="color:var(--cyan)">▶ in uso</b>' : "", `${ICON[m.origin]} ${fmt.esc(m.provider)}`, status,
        c.fit && c.fit.label, st ? `${st.ok} risposte · ~${seconds(st.avg_ms)}${st.fail ? ` · ${st.fail} errori` : ""}` : ""].filter(Boolean).join(" · ");
      return A.prioItem(m.name, i, c.label && c.label !== m.name ? `${c.label} · ${m.model}` : m.model, sub, !m.available, false);
    }).join("") + (d[`${kind}_custom`] ? "" : `<div class="muted-note" style="margin:4px 6px">Automatico: scelto da Jarvis in base all'hardware (${kind === "chat" ? "veloce" : "potente"}: ${fmt.esc(kind === "chat" ? d.fast : d.main)}).</div>`);
  }

  function catalogItem(d, m, inChat, inDeep) {
    return `<div class="cat-item"><div>
        <div class="nm">${fmt.esc(m.label)} <span class="faint mono" style="font-size:11px">${fmt.esc(m.name)}${m.size_gb ? ` · ${m.size_gb} GB` : ""}</span>
          ${m.name === d.suggested.chat ? '<span class="badge ok">consigliato ⚡</span>' : ""}${m.name === d.suggested.deep ? '<span class="badge ok">consigliato 🧠</span>' : ""}</div>
        <div class="nt">${fmt.esc(m.notes || "")}</div>
        <div class="fit ${m.fit.level}">${fmt.esc(m.fit.label)}${m.installed ? " · ✓ scaricato" : ""}</div></div>
      <div class="actions" style="justify-content:flex-end">
        <button class="btn sm" data-add="chat" data-m="${fmt.esc(m.name)}" ${inChat.has(m.name) ? "disabled" : ""} title="Aggiungi alla conversazione veloce">+ ⚡</button>
        <button class="btn sm" data-add="deep" data-m="${fmt.esc(m.name)}" ${inDeep.has(m.name) ? "disabled" : ""} title="Aggiungi al ragionamento">+ 🧠</button>
        ${m.installed ? "" : `<button class="btn sm primary" data-dl="${fmt.esc(m.name)}" data-size="${m.size_gb || ""}">Scarica</button>`}</div></div>`;
  }

  function renderBrains() {
    const d = brainData, cat = Object.fromEntries(d.catalog.map((m) => [m.name, m]));
    $("br-routing").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.r === d.routing));
    $("br-now-chat").innerHTML = nowCard("chat", d.active.chat, d.chat);
    $("br-now-deep").innerHTML = nowCard("deep", d.active.deep, d.deep);
    const l = d.last_used || {};
    $("br-last").innerHTML = l.model ? `Ultima risposta: <b>${fmt.esc(l.model)}</b> ${originBadge(l)} in ${seconds(l.ms)}` : "";
    $("br-chat").innerHTML = priorityList(d, "chat", cat); $("br-deep").innerHTML = priorityList(d, "deep", cat);
    const hw = d.hardware || {};
    $("br-hw").textContent = `${hw.ram_gb || "?"} GB RAM · ${hw.gpu ? `${hw.gpu} ${hw.vram_gb} GB` : "solo CPU"}`;
    const inChat = new Set(d.chat.map((m) => m.name)), inDeep = new Set(d.deep.map((m) => m.name));
    $("br-catalog").innerHTML = d.catalog.map((m) => catalogItem(d, m, inChat, inDeep)).join("");
  }

  async function saveBrains(body) {
    try { brainData = await A.api("PUT", "/api/brains", body); renderBrains(); } catch (e) { A.toast(e.message, true); loadBrains(); }
  }

  async function addTo(kind, name, first = false) {
    if (!brainData) await loadBrains();
    const list = brainData[kind].map((x) => x.name);
    if (list.includes(name)) { A.toast("È già nella lista"); return; }
    await saveBrains({ [kind]: first ? [name, ...list] : [...list, name] });
    A.toast(`Aggiunto ${first ? "in cima" : "in coda"} a ${kind === "chat" ? "⚡ Conversazione" : "🧠 Ragionamento"}: trascinalo per cambiarne la priorità`);
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
    A.makeSortable($("br-chat"), (items) => saveBrains({ chat: items }));
    A.makeSortable($("br-deep"), (items) => saveBrains({ deep: items }));
    $("br-routing").addEventListener("click", (e) => { const b = e.target.closest("[data-r]"); if (b) saveBrains({ routing: b.dataset.r }).then(() => A.toast("Instradamento aggiornato")); });
    document.querySelectorAll("[data-br-reset]").forEach((b) => b.addEventListener("click", () => saveBrains({ [b.dataset.brReset]: [] }).then(() => A.toast("Lista tornata automatica"))));
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
        $("br-res").innerHTML = `${r.kind === "chat" ? "⚡ Conversazione" : "🧠 Ragionamento"} <span class="faint">— ${fmt.esc(r.reason)} · risponderà ${fmt.esc(r.models[0] || "nessuno")}${r.models.length > 1 ? `, poi in ordine: ${r.models.slice(1).map(fmt.esc).join(" → ")}` : ""}</span>`;
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
  A.tab("models", { title: "Cervello", init() { init(); if (A.brainCloud) A.brainCloud.init(); if (A.brainServers) A.brainServers.init(); }, load() { loadModels(); loadBrains(); loadOllama(); if (A.brainCloud) A.brainCloud.load(); if (A.brainServers) A.brainServers.load(); }, onState });
})();

  // === AGENT MAPPING LOGIC ===
  async function loadAgentMap() {
    try {
      const res = await fetch('/api/brain/agent_map', { headers: { "Authorization": "Bearer " + localStorage.getItem("token") } });
      if (!res.ok) return;
      const data = await res.json();
      
      const selects = document.querySelectorAll(".agent-map-select");
      
      // Popola le option dei select con i modelli disponibili
      const allModels = window._lastModels || []; // Presupponendo che i modelli siano salvati
      // Facciamo una fetch dei modelli se non ci sono
      const mRes = await fetch('/api/models', { headers: { "Authorization": "Bearer " + localStorage.getItem("token") } });
      const mData = await mRes.json();
      
      let optionsHtml = '<option value="">-- Predefinito --</option>';
      for (const m of mData.models || []) {
        optionsHtml += `<option value="${m.id}">${m.name} (${m.provider})</option>`;
      }
      
      selects.forEach(sel => {
        sel.innerHTML = optionsHtml;
        const mappedAgentId = sel.id.replace("map-", ""); // es. ricercatore
        
        let dbId = mappedAgentId;
        if (dbId === 'studio') dbId = 'skill_synthesizer';
        if (dbId === '3d') dbId = 'genera_modello_3d';
        if (dbId === 'coder') dbId = 'agent_self_healing_coder';
        
        if (data.map && data.map[dbId]) {
           sel.value = data.map[dbId];
        }
      });
    } catch (e) {}
  }
  
  if ($("save-agent-map")) {
      $("save-agent-map").addEventListener("click", async () => {
          $("save-agent-map").disabled = true;
          const map = {};
          document.querySelectorAll(".agent-map-select").forEach(sel => {
              if (sel.value) {
                  let dbId = sel.id.replace("map-", "");
                  if (dbId === 'studio') dbId = 'skill_synthesizer';
                  if (dbId === '3d') dbId = 'genera_modello_3d';
                  if (dbId === 'coder') dbId = 'agent_self_healing_coder';
                  map[dbId] = sel.value;
              }
          });
          
          const res = await fetch('/api/brain/agent_map', {
              method: 'POST',
              headers: { "Content-Type": "application/json", "Authorization": "Bearer " + localStorage.getItem("token") },
              body: JSON.stringify({ map })
          });
          
          if (res.ok) {
              $("agent-map-res").textContent = "✓ Mappatura salvata con successo";
              $("agent-map-res").style.color = "var(--cyan)";
          } else {
              $("agent-map-res").textContent = "Errore durante il salvataggio";
          }
          $("save-agent-map").disabled = false;
          setTimeout(() => { $("agent-map-res").textContent = ""; }, 3000);
      });
      
      // Load map on boot
      loadAgentMap();
  }
