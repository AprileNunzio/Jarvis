(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  const LABELS = { temperature: "Creatività", top_p: "Top-p", max_tokens: "Lunghezza massima", reasoning: "Ragionamento", timeout: "Attesa (s)" };
  const NAMES = { "": "predefinito", minimal: "minimo", low: "basso", medium: "medio", high: "alto" };
  let data = null, filter = "all";
  const modelCache = {};

  const ref = (pid, model) => `cloud:${pid}/${model}`;

  function optionSelect(p, name) {
    if (name === "reasoning" && !p.reasoning) return "";
    const cur = p.options[name] || "";
    const opts = data.choices[name].map((v) => `<option value="${fmt.esc(v)}" ${v === cur ? "selected" : ""}>${fmt.esc(NAMES[v] ?? v)}</option>`).join("");
    return `<label>${LABELS[name]}<select data-opt="${name}">${opts}</select></label>`;
  }

  const ctx = (n) => (n >= 1e6 ? `${+(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${Math.round(n / 1e3)}k` : "");

  function modelLabel(m, d) {
    if (!d) return m;
    const price = d.price_in != null && d.price_out != null ? `$${d.price_in}/${d.price_out}` : "";
    return [m, ctx(d.context), price, d.vision ? "👁" : "", d.reasoning ? "🧠" : ""].filter(Boolean).join(" · ");
  }

  function modelOptions(p, query = "", chosen = p.model) {
    const info = modelCache[p.id] || {}, q = query.toLowerCase();
    const all = info.models || [];
    const list = all.filter((m) => !q || m.toLowerCase().includes(q) || m === chosen);
    if (chosen && !all.includes(chosen)) list.unshift(chosen);
    return list.map((m) => `<option value="${fmt.esc(m)}" ${m === chosen ? "selected" : ""}>${m === p.model ? "★ " : ""}${fmt.esc(modelLabel(m, (info.details || {})[m]))}</option>`).join("")
      || '<option value="">nessun modello</option>';
  }

  function modelSummary(p) {
    const info = modelCache[p.id] || {};
    const n = (info.models || []).length;
    return n ? `${n} modelli · fonte: ${info.source}${info.source === "catalogo pubblico" ? " (collega la chiave per la lista ufficiale)" : ""}` : "";
  }

  function card(p) {
    const badge = p.configured ? '<span class="badge ok">collegato</span>' : p.has_key ? '<span class="badge warn">incompleto</span>' : '<span class="badge">non collegato</span>';
    const used = [...A.brainRoles.usedRefs()].filter((r) => r.startsWith(`cloud:${p.id}/`)).length;
    const url = `<label class="wide">Indirizzo del servizio<input data-f="base_url" value="${fmt.esc(p.base_url)}" placeholder="https://…/v1"></label>`;
    return `<div class="panel cl-card" data-pid="${p.id}">
      <div class="cl-head"><span class="cl-name">${fmt.esc(p.name)}</span><span>${badge}${used ? ` <span class="badge ok">in uso · ${used}</span>` : ""}</span></div>
      <div class="cl-notes">${fmt.esc(p.notes || "")}${p.key_url ? ` <a href="${fmt.esc(p.key_url)}" target="_blank" rel="noopener noreferrer">Ottieni la chiave ↗</a>` : ""}</div>
      <div class="cl-fields">
        <label class="wide">Chiave API${p.key_optional ? " (facoltativa)" : ""}<input type="password" data-f="key" autocomplete="off" placeholder="${p.has_key ? fmt.esc(p.key_hint) + " — lascia vuoto per mantenerla" : "incolla la chiave"}"></label>
        ${p.needs_url ? url : ""}
        ${["temperature", "top_p", "max_tokens", "reasoning", "timeout"].map((n) => optionSelect(p, n)).join("")}
      </div>
      <div class="cl-models"><input data-mfilter placeholder="Filtra modelli…" autocomplete="off"><select data-model>${modelOptions(p)}</select><button class="btn sm" data-act="refresh" title="Aggiorna l'elenco dal servizio">↻</button></div>
      <div class="cl-count">${fmt.esc(modelSummary(p))} · $ = dollari per milione di token in/out</div>
      <div class="actions">
        <button class="btn sm primary" data-act="save">Salva</button>
        <button class="btn sm" data-act="test" ${p.configured ? "" : "disabled"}>Prova</button>
        ${A.brainRoles.all().map((r) => `<button class="btn sm" data-add="${r.id}" ${p.configured ? "" : "disabled"} title="Aggiungi a ${fmt.esc(r.label)}">+ ${r.icon}</button>`).join("")}
        ${p.has_key ? '<button class="btn sm danger" data-act="forget">Rimuovi chiave</button>' : ""}
      </div>
      <div class="cl-result" data-result>${fmt.esc(modelCache[p.id]?.error || "")}</div>
    </div>`;
  }

  function render() {
    const q = $("cl-search").value.trim().toLowerCase();
    const list = data.providers.filter((p) => (filter === "all" || p.configured) && (!q || p.name.toLowerCase().includes(q)));
    $("cl-grid").innerHTML = list.map(card).join("") || '<div class="faint">Nessun fornitore corrisponde.</div>';
    const configured = data.providers.filter((p) => p.configured);
    const preferred = configured.filter((p) => p.model).map((p) => [ref(p.id, p.model), `★ ${p.name} · ${p.model}`]);
    const choices = [...preferred, ...configured.flatMap((p) => (modelCache[p.id]?.models || []).filter((m) => m !== p.model).map((m) => [ref(p.id, m), `${p.name} · ${m}`]))];
    const opts = choices.map(([v, l]) => `<option value="${fmt.esc(v)}">${fmt.esc(l)}</option>`).join("") || '<option value="">collega prima un fornitore</option>';
    $("cl-only-chat").innerHTML = opts; $("cl-only-deep").innerHTML = opts;
  }

  async function loadModels(pid, refresh = false) {
    try { modelCache[pid] = await A.api("GET", `/api/cloud/${pid}/models${refresh ? "?refresh=true" : ""}`); }
    catch (e) { modelCache[pid] = { models: [], error: e.message }; }
  }

  async function load() {
    try { data = await A.api("GET", "/api/cloud"); } catch (e) { $("cl-grid").innerHTML = `<div class="faint">${fmt.esc(e.message)}</div>`; return; }
    await Promise.all(data.providers.map((p) => loadModels(p.id)));
    render();
  }

  function collect(el) {
    const body = { options: {}, model: el.querySelector("[data-model]").value };
    const key = el.querySelector('[data-f="key"]').value.trim();
    if (key) body.key = key;
    const url = el.querySelector('[data-f="base_url"]');
    if (url) body.base_url = url.value.trim();
    el.querySelectorAll("[data-opt]").forEach((s) => { if (s.value) body.options[s.dataset.opt] = s.value; });
    return body;
  }

  async function addTo(kind, value) {
    await A.brain.addTo(kind, value, true);
    load();
  }

  async function act(el, action, roleId) {
    const pid = el.dataset.pid, out = el.querySelector("[data-result]"), model = el.querySelector("[data-model]").value;
    out.className = "cl-result"; out.textContent = "…";
    try {
      if (action === "save") {
        const saved = await A.api("PUT", `/api/cloud/${pid}`, collect(el));
        await loadModels(pid, true);
        const inUse = [...A.brainRoles.usedRefs()].some((r) => r.startsWith(`cloud:${pid}/`));
        A.toast(inUse || !saved.configured ? `Salvato: ${saved.model || "nessun modello"}` : `Salvato ${saved.model}. Premi ${A.brainRoles.addHint()} perché Jarvis lo usi`);
        return load();
      }
      if (action === "forget") { if (!confirm("Rimuovere la chiave?")) return; await A.api("PUT", `/api/cloud/${pid}`, { key: "" }); return load(); }
      if (action === "refresh") { await loadModels(pid, true); return render(); }
      if (action === "add") { out.textContent = ""; return addTo(roleId, ref(pid, model)); }
      if (action === "test") {
        const r = await A.api("POST", `/api/cloud/${pid}/test`, { model });
        out.className = `cl-result ${r.ok ? "ok" : "err"}`;
        out.textContent = r.ok ? `✓ ${model} ha risposto in ${(r.ms / 1000).toFixed(1)} s: «${r.reply}»` : `✗ ${r.error}`;
      }
    } catch (e) { out.className = "cl-result err"; out.textContent = e.message; }
  }

  function init() {
    $("cl-grid").addEventListener("click", (e) => { const b = e.target.closest("[data-act],[data-add]"); if (b) act(b.closest("[data-pid]"), b.dataset.act || "add", b.dataset.add); });
    $("cl-search").addEventListener("input", render);
    $("cl-grid").addEventListener("input", (e) => {
      if (!e.target.matches("[data-mfilter]")) return;
      const card = e.target.closest("[data-pid]"), p = data.providers.find((x) => x.id === card.dataset.pid);
      const select = card.querySelector("[data-model]");
      select.innerHTML = modelOptions(p, e.target.value.trim(), select.value);
    });
    $("cl-show").addEventListener("click", (e) => { const b = e.target.closest("[data-f]"); if (!b) return; filter = b.dataset.f; $("cl-show").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b)); render(); });
    $("cl-only-btn").addEventListener("click", async () => {
      const chat = $("cl-only-chat").value, deep = $("cl-only-deep").value;
      if (!chat || !deep) return A.toast("Collega prima almeno un fornitore", true);
      if (!confirm("Jarvis userà solo questi cervelli cloud, senza modelli locali. Procedere?")) return;
      try { await A.api("POST", "/api/cloud/only", { chat: [chat], deep: [deep] }); A.toast("Jarvis ora ragiona solo nel cloud"); A.brain.reload(); load(); } catch (e) { A.toast(e.message, true); }
    });
  }

  A.brainCloud = { init, load };
})();
