(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  const when = (t) => (t ? new Date(t * 1000).toLocaleString("it-IT", { dateStyle: "short", timeStyle: "medium" }) : "mai");
  const BADGE = { completata: "ok", "in corso": "info", errore: "bad", fermata: "warn", interrotta: "warn", "in coda": "info", "condizioni non soddisfatte": "" };
  let data = null, catalog = null, current = null, dirty = false, jsonView = false, timer = null, runFilter = "";

  const api = (method, url, body) => A.api(method, url, body);

  function status(d) {
    $("am-status").textContent = `${d.enabled ? "Motore attivo" : "Motore disattivato"} · ${d.status} · ${d.automations.length} automazioni, `
      + `${d.automations.filter((a) => a.enabled !== false).length} attive · ${d.active.length} in corso`;
  }

  function list(d) {
    const q = $("am-search").value.trim().toLowerCase();
    const items = d.automations.filter((a) => !q || a.name.toLowerCase().includes(q) || (a.tags || []).some((t) => t.toLowerCase().includes(q)));
    const icons = (a) => (a.triggers || []).map((t) => (catalog.triggers[t.type] || {}).icon || "?").join("");
    $("am-list").innerHTML = items.map((a) => `<div class="am-item ${a.enabled === false ? "off" : ""} ${current && current.id === a.id ? "sel" : ""}" data-id="${fmt.esc(a.id)}">
        <label class="am-switch" title="Attiva o disattiva"><input type="checkbox" data-toggle${a.enabled !== false ? " checked" : ""}><i></i></label>
        <div class="am-item-main"><b>${fmt.esc(a.name)}</b> <span class="faint">${icons(a)}</span>
          ${(a.tags || []).map((t) => `<span class="badge">${fmt.esc(t)}</span>`).join(" ")}
          <div class="faint">${(a.triggers || []).length} inneschi · ${(a.conditions || []).length} condizioni · ${(a.actions || []).length} azioni · ${a.runs || 0} esecuzioni
            · ultima ${when(a.last_run)} ${a.last_status ? `<span class="badge ${BADGE[a.last_status] || ""}">${fmt.esc(a.last_status)}</span>` : ""}</div>
          ${a.last_error ? `<div class="am-err-line">${fmt.esc(a.last_error)}</div>` : ""}</div>
        <div class="actions"><button class="btn sm" data-run>▶</button><button class="btn sm" data-edit>Modifica</button>
          <button class="btn sm" data-dup>⧉</button><button class="btn sm" data-hist>Storico</button><button class="btn sm danger" data-del>✕</button></div></div>`).join("")
      || '<div class="faint">Nessuna automazione. Ne crei una nuova, parta da un modello o la descriva a parole qui sopra.</div>';
  }

  function active(d) {
    const box = $("am-active");
    const waiting = new Set(d.waiting.map((w) => w.run));
    box.hidden = !d.active.length;
    box.innerHTML = `<div class="panel-title">In corso (${d.active.length})</div>` + d.active.map((r) => `<div class="am-run-line" data-run="${fmt.esc(r.id)}">
      <span class="badge info">${fmt.esc(r.status)}</span><b>${fmt.esc(r.name)}</b><span class="faint">${fmt.esc(r.trigger.label || r.trigger.type || "")} · ${r.steps} passi · ${Math.round(r.ms / 1000)} s</span>
      ${r.waiting ? `<span class="am-wait">⏳ ${fmt.esc(r.waiting)}</span>` : ""}${waiting.has(r.id) ? '<span class="badge warn">aspetta una risposta a voce</span>' : ""}
      <span class="actions"><button class="btn sm" data-trace>Traccia</button><button class="btn sm danger" data-stop>Ferma</button></span></div>`).join("");
  }

  async function runs() {
    const q = runFilter ? `?automation=${encodeURIComponent(runFilter)}` : "";
    const r = await api("GET", `/api/automations/runs${q}`);
    const name = runFilter && data ? (data.automations.find((a) => a.id === runFilter) || {}).name : "";
    $("am-runs-filter").innerHTML = runFilter ? `solo «${fmt.esc(name || runFilter)}» <button class="btn sm" id="am-runs-all">Tutte</button>` : "";
    $("am-runs").innerHTML = r.runs.map((x) => `<div class="am-run-line" data-run="${fmt.esc(x.id)}"><span class="badge ${BADGE[x.status] || ""}">${fmt.esc(x.status)}</span>
        <b>${fmt.esc(x.name)}</b><span class="faint">${when(x.started)} · ${fmt.esc((x.trigger || {}).label || (x.trigger || {}).type || "")} · ${x.steps} passi · ${x.ms} ms</span>
        ${x.error ? `<span class="am-err-line">${fmt.esc(x.error)}</span>` : ""}<span class="actions"><button class="btn sm" data-trace>Traccia</button></span></div>`).join("")
      || '<div class="faint">Ancora nessuna esecuzione.</div>';
  }

  async function trace(rid) {
    const r = await api("GET", `/api/automations/runs/${encodeURIComponent(rid)}`);
    const box = $("am-trace");
    box.hidden = false;
    const vars = Object.entries(r.vars || {}).map(([k, v]) => `${fmt.esc(k)} = ${fmt.esc(typeof v === "object" ? JSON.stringify(v) : v)}`).join(" · ");
    box.innerHTML = `<div class="am-ed-head"><b>${fmt.esc(r.name)} — ${fmt.esc(r.status)}</b><button class="btn sm" data-close>Chiudi</button></div>
      <div class="faint">${when(r.started)} · innesco: ${fmt.esc((r.trigger || {}).label || (r.trigger || {}).type || "")}${r.error ? ` · <span class="am-err-line">${fmt.esc(r.error)}</span>` : ""}</div>
      ${vars ? `<div class="mono faint">${vars}</div>` : ""}
      <div class="am-steps">${(r.trace || []).map((s) => `<div class="am-step ${s.ok ? "ok" : "bad"} ${s.kind === "condizione" ? "cond" : ""}">
        <span class="mono">${fmt.esc(s.path || "·")}</span><span>${s.kind === "condizione" ? "◇" : "▸"} ${fmt.esc(s.type)}</span>
        <span>${fmt.esc(s.detail || "")}</span><span class="faint">${s.ms != null ? s.ms + " ms" : ""}</span></div>`).join("")}</div>`;
    box.querySelector("[data-close]").onclick = () => { box.hidden = true; };
    box.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function side() {
    $("am-globals").textContent = Object.entries(catalog.globals || {}).map(([k, v]) => `${k} = ${JSON.stringify(v)}`).join("\n") || "nessuna";
    $("am-events").innerHTML = (catalog.events_recent || []).slice().reverse().slice(0, 15).map((e) => `<div class="am-event"><span class="mono">${fmt.esc(e.name)}</span>
      <span class="faint">${new Date(e.at * 1000).toLocaleTimeString("it-IT")}</span><span class="faint mono">${fmt.esc(JSON.stringify(e.data).slice(0, 90))}</span></div>`).join("") || '<div class="faint">nessuno</div>';
    $("am-entities").innerHTML = catalog.entities.map((e) => `<option value="${fmt.esc(e.id)}">${fmt.esc(e.name)} = ${fmt.esc(e.state)}</option>`).join("");
  }

  function draw() {
    const form = $("am-form"), json = $("am-json");
    form.hidden = jsonView; json.hidden = !jsonView;
    $("am-view").textContent = jsonView ? "Vista a blocchi" : "Vista JSON";
    $("am-ed-title").textContent = (current.id ? "Modifica: " : "Nuova: ") + (current.name || "senza nome") + (dirty ? " •" : "");
    if (jsonView) json.value = JSON.stringify(AutomationEditor.clean(current), null, 2);
    else AutomationEditor.render(form, current, catalog, (re) => { dirty = true; $("am-ed-title").textContent = (current.id ? "Modifica: " : "Nuova: ") + (current.name || "senza nome") + " •"; if (re) draw(); });
  }

  function syncJson() {
    if (!jsonView) return true;
    try { current = JSON.parse($("am-json").value); return true; } catch (e) { showErrors([`JSON non valido: ${e.message}`]); return false; }
  }

  function showErrors(errors) {
    const box = $("am-errors");
    box.hidden = !errors.length;
    box.innerHTML = errors.map((e) => `<div>⚠ ${fmt.esc(e)}</div>`).join("");
  }

  function open(a) {
    current = JSON.parse(JSON.stringify(a)); dirty = false; showErrors([]);
    $("am-editor").hidden = false; $("am-editor").parentElement.classList.add("editing"); draw();
    $("am-editor").scrollIntoView({ behavior: "smooth", block: "start" });
    if (data) list(data);
  }

  async function save() {
    if (!syncJson()) return;
    const body = AutomationEditor.clean(current);
    const check = await api("POST", "/api/automations/validate", body);
    if (!check.ok) { showErrors(check.errors); A.toast("Ci sono errori da correggere", true); return; }
    try {
      const saved = current.id ? await api("PUT", `/api/automations/${encodeURIComponent(current.id)}`, body) : await api("POST", "/api/automations", body);
      A.toast(`Salvata «${saved.name}»`); showErrors([]); open(saved); load();
    } catch (err) { showErrors([err.message]); }
  }

  async function load() {
    try {
      [data, catalog] = await Promise.all([api("GET", "/api/automations"), catalog && Date.now() - (catalog._at || 0) < 20000 ? catalog : api("GET", "/api/automations/catalog")]);
      catalog._at = catalog._at || Date.now();
      status(data); list(data); active(data); side(); runs();
      if (!$("am-template").options[1]) $("am-template").innerHTML += catalog.templates.map((t) => `<option value="${t.index}" title="${fmt.esc(t.description)}">${fmt.esc(t.name)}</option>`).join("");
    } catch (e) { $("am-status").textContent = e.message; }
  }

  function init() {
    $("am-search").addEventListener("input", () => data && list(data));
    $("am-new").addEventListener("click", () => open({ name: "", mode: "single", enabled: true, triggers: [], conditions: [], actions: [], variables: {}, tags: [] }));
    $("am-template").addEventListener("change", async (e) => {
      if (e.target.value === "") return;
      try { const a = await api("POST", `/api/automations/templates/${e.target.value}`); A.toast(`Creata da modello, disattivata: «${a.name}». Adatti i dispositivi e la attivi.`); await load(); open(a); }
      catch (err) { A.toast(err.message, true); }
      e.target.value = "";
    });
    $("am-gen").addEventListener("click", async () => {
      const text = $("am-gen-text").value.trim(); if (!text) return;
      const b = $("am-gen"); b.disabled = true; b.textContent = "Progetto…";
      try {
        const r = await api("POST", "/api/automations/generate", { text });
        open({ ...r.automation, enabled: false }); dirty = true; draw(); showErrors(r.errors || []);
        A.toast(r.errors && r.errors.length ? "Bozza con errori da correggere" : "Bozza pronta: controlli e salvi");
      } catch (err) { A.toast(err.message, true); }
      b.disabled = false; b.textContent = "Progetta";
    });
    $("am-view").addEventListener("click", () => { if (!syncJson()) return; jsonView = !jsonView; draw(); });
    $("am-save").addEventListener("click", save);
    $("am-close").addEventListener("click", () => { if (dirty && !confirm("Ci sono modifiche non salvate. Chiudere?")) return; $("am-editor").hidden = true; $("am-editor").parentElement.classList.remove("editing"); current = null; data && list(data); });
    $("am-validate").addEventListener("click", async () => {
      if (!syncJson()) return;
      const r = await api("POST", "/api/automations/validate", AutomationEditor.clean(current));
      showErrors(r.errors); if (r.ok) A.toast("Tutto corretto");
    });
    $("am-try").addEventListener("click", async () => {
      if (!current.id) { A.toast("Salvi prima l'automazione", true); return; }
      if (dirty) await save();
      const r = await api("POST", `/api/automations/${encodeURIComponent(current.id)}/run`, { check: false });
      A.toast(r.ok ? "Avviata: segua la traccia qui sotto" : r.message, !r.ok);
      if (r.ok) setTimeout(() => { load(); trace(r.run); }, 1200);
    });
    $("am-list").addEventListener("click", async (e) => {
      const item = e.target.closest("[data-id]"); if (!item) return;
      const id = item.dataset.id, url = `/api/automations/${encodeURIComponent(id)}`, a = data.automations.find((x) => x.id === id);
      try {
        if (e.target.closest("[data-toggle]")) { const r = await api("POST", `${url}/toggle`, { enabled: e.target.checked }); A.toast(r.message); load(); return; }
        if (e.target.closest("[data-run]")) { const r = await api("POST", `${url}/run`, {}); A.toast(r.ok ? "Avviata" : r.message, !r.ok); setTimeout(load, 1500); }
        else if (e.target.closest("[data-dup]")) { const c = await api("POST", `${url}/duplicate`); A.toast("Duplicata (disattivata)"); await load(); open(c); }
        else if (e.target.closest("[data-hist]")) { runFilter = id; runs(); $("am-runs").scrollIntoView({ behavior: "smooth" }); }
        else if (e.target.closest("[data-del]")) { if (confirm(`Eliminare «${a.name}»?`)) { await api("DELETE", url); if (current && current.id === id) { $("am-editor").hidden = true; current = null; } load(); } }
        else if (e.target.closest("[data-edit]") || !e.target.closest("button,input,label")) open(a);
      } catch (err) { A.toast(err.message, true); }
    });
    const runClick = async (e) => {
      if (e.target.id === "am-runs-all") { runFilter = ""; runs(); return; }
      const line = e.target.closest("[data-run]"); if (!line) return;
      if (e.target.closest("[data-stop]")) { await api("POST", `/api/automations/runs/${encodeURIComponent(line.dataset.run)}/stop`); A.toast("Fermata"); setTimeout(load, 800); return; }
      trace(line.dataset.run);
    };
    $("am-runs").addEventListener("click", runClick);
    $("am-runs-filter").addEventListener("click", runClick);
    $("am-active").addEventListener("click", runClick);
    $("am-export").addEventListener("click", async () => {
      const d = await api("GET", "/api/automations/export");
      const link = document.createElement("a");
      link.href = URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: "application/json" }));
      link.download = `jarvis-automazioni-${new Date().toISOString().slice(0, 10)}.json`; link.click();
    });
    $("am-import").addEventListener("change", async (e) => {
      const file = e.target.files[0]; if (!file) return;
      try {
        const r = await api("POST", "/api/automations/import", JSON.parse(await file.text()));
        A.toast(`Importate ${r.imported.length} (disattivate)${r.failed.length ? `, ${r.failed.length} non valide` : ""}`, !!r.failed.length); load();
      } catch (err) { A.toast(err.message, true); }
      e.target.value = "";
    });
    $("am-expr-go").addEventListener("click", async () => {
      const r = await api("POST", "/api/automations/expr", { expr: $("am-expr").value });
      $("am-expr-out").textContent = r.ok ? `= ${JSON.stringify(r.value)}` : `⚠ ${r.error}`;
    });
  }

  A.tab("automations", {
    title: "Automazioni", init,
    load() { load(); clearInterval(timer); timer = setInterval(() => { if (A.isOn("automations")) { api("GET", "/api/automations").then((d) => { data = d; status(d); active(d); if (!current) list(d); }).catch(() => {}); } }, 4000); },
    leave() { clearInterval(timer); },
  });
})();
