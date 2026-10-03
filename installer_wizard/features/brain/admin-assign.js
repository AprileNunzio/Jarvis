(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  const esc = fmt.esc;
  const ICON = { cloud: "☁", server: "🖧", local: "🖥" };
  const KEEP = [["", "Predefinito"], ["5m", "5 minuti"], ["30m", "30 minuti"], ["1h", "1 ora"], ["6h", "6 ore"], ["24h", "24 ore"], ["-1", "Sempre"]];
  const ORIGIN_LABEL = { local: "Questo server", server: "Altri server", cloud: "Cloud" };
  let data = null, keep = { overrides: {} }, editing = null, draft = null;

  const label = (ref) => (data.pool.find((p) => p.ref === ref) || { label: ref }).label;
  const roleName = (id) => { const r = data.roles.find((x) => x.id === id); return r ? `${r.icon} ${r.label}` : id; };

  function chips(chain) {
    if (!chain.length) return '<span class="warn">nessun cervello disponibile</span>';
    return chain.map((c, i) => `<span class="as-chip ${c.available ? "" : "off"} ${i === 0 ? "first" : ""}" title="${esc(c.provider)}">${i === 0 ? "▶ " : `${i + 1}· `}${ICON[c.origin] || ""} ${esc(c.model)}</span>`).join("");
  }

  function ownList() {
    if (!draft.order.length) return '<div class="faint">Nessun cervello dedicato: usa la lista del ruolo.</div>';
    return draft.order.map((ref, i) => `<div class="as-own"><span class="mono">${esc(label(ref))}</span><span class="actions">
      <button class="btn sm" data-up="${i}" ${i ? "" : "disabled"}>↑</button><button class="btn sm" data-down="${i}" ${i < draft.order.length - 1 ? "" : "disabled"}>↓</button>
      <button class="btn sm danger" data-rm="${i}">✕</button></span></div>`).join("");
  }

  function pickOptions() {
    return ["local", "server", "cloud"].map((origin) => {
      const items = data.pool.filter((p) => p.origin === origin && !draft.order.includes(p.ref));
      if (!items.length) return "";
      return `<optgroup label="${ORIGIN_LABEL[origin]}">${items.map((p) => `<option value="${esc(p.ref)}">${esc(p.label)}${p.available ? "" : " (non disponibile)"}</option>`).join("")}</optgroup>`;
    }).join("");
  }

  function editor(c) {
    const roles = [["", `Predefinito — ${roleName(c.default_role)}`], ...data.roles.map((r) => [r.id, `${r.icon} ${r.label}`])];
    const options = roles.map(([v, l]) => `<option value="${v}" ${draft.role === v ? "selected" : ""}>${esc(l)}</option>`).join("");
    const group = `mode-${esc(c.id)}`;
    return `<div class="as-edit">
      <label>Lista di riserva (ruolo)<select data-role>${options}</select></label>
      <div class="as-sub">Cervelli dedicati, in ordine di priorità</div>${ownList()}
      <div class="as-add"><select data-pick><option value="">Aggiungi un modello o un server…</option>${pickOptions()}</select><button class="btn sm" data-add>+ Aggiungi</button></div>
      <label class="as-mode"><input type="radio" name="${group}" value="first" ${draft.mode !== "only" ? "checked" : ""}> Prima i miei, poi la lista del ruolo se non rispondono</label>
      <label class="as-mode"><input type="radio" name="${group}" value="only" ${draft.mode === "only" ? "checked" : ""}> Solo i miei, nessun ripiego</label>
      <div class="actions"><button class="btn primary sm" data-save>Salva</button><button class="btn sm" data-cancel>Annulla</button>
      <button class="btn sm danger" data-reset>Torna al predefinito</button></div></div>`;
  }

  function row(c) {
    const custom = c.assignment.role || c.assignment.order.length;
    return `<div class="as-row ${custom ? "custom" : ""}" data-id="${esc(c.id)}">
      <div class="as-main"><div class="as-name">${esc(c.label)} ${custom ? '<span class="badge">personalizzato</span>' : ""}
        <span class="as-side">${c.side === "core" ? "Core" : "Supervisore"}</span></div>
        <div class="faint">${esc(c.hint)}</div>
        <div class="as-chain">${chips(c.chain)}</div></div>
      <button class="btn sm" data-edit-open>${editing === c.id ? "Chiudi" : "Cambia"}</button>
      ${editing === c.id ? editor(c) : ""}</div>`;
  }

  function keepPanel() {
    const refs = [...new Set([...data.components.flatMap((c) => c.chain.slice(0, 2).map((x) => x.ref)), ...Object.keys(keep.overrides)])];
    const rows = refs.map((ref) => `<div class="as-keep"><span class="mono">${esc(label(ref))}</span><select data-keep="${esc(ref)}">${KEEP.map(([v, l]) => `<option value="${v}" ${(keep.overrides[ref] || "") === v ? "selected" : ""}>${l}</option>`).join("")}</select></div>`).join("");
    return `<div class="panel-title">Permanenza in memoria</div>
      <div class="muted-note">Quanto a lungo il modello resta caricato dopo l'ultima risposta: più è lungo, più Jarvis risponde subito senza ricaricarlo. Vale per questo server e per gli altri server Ollama.</div>${rows || '<div class="faint">Nessun modello in uso.</div>'}`;
  }

  function render() {
    const groups = [...new Set(data.components.map((c) => c.group))];
    const body = groups.map((g) => `<div class="as-group"><div class="as-group-title">${esc(g)}</div>${data.components.filter((c) => c.group === g).map(row).join("")}</div>`).join("");
    $("br-assign").innerHTML = `<div class="panel"><div class="panel-title">Assegnazioni per componente</div>
      <div class="muted-note">Ogni agente e funzione può avere un proprio cervello: un modello locale, un altro server o un servizio cloud, con priorità e ripiego. Ciò che non personalizzi segue la lista del suo ruolo.</div>${body}</div>
      <div class="panel">${keepPanel()}</div>`;
  }

  async function load() {
    try {
      [data, keep] = await Promise.all([A.api("GET", "/api/brains/assignments"), A.api("GET", "/api/brains/keepalive")]);
    } catch (e) { $("br-assign").innerHTML = `<div class="faint">${esc(e.message)}</div>`; return; }
    render();
  }

  async function save(id, value) {
    try {
      const r = await A.api("PUT", "/api/brains/assignments", { updates: { [id]: value } });
      data.components = r.components; editing = null; draft = null; render();
      A.toast("Assegnazione salvata: già attiva");
    } catch (e) { A.toast(e.message, true); }
  }

  function swap(i, j) { [draft.order[i], draft.order[j]] = [draft.order[j], draft.order[i]]; render(); }

  function onClick(e) {
    const rowEl = e.target.closest(".as-row"); if (!rowEl) return;
    const id = rowEl.dataset.id, c = data.components.find((x) => x.id === id), t = e.target;
    if (t.closest("[data-edit-open]")) {
      editing = editing === id ? null : id;
      draft = editing ? { role: c.assignment.role, order: [...c.assignment.order], mode: c.assignment.mode === "only" ? "only" : "first" } : null;
      return render();
    }
    if (editing !== id) return;
    if (t.dataset.up !== undefined) swap(+t.dataset.up - 1, +t.dataset.up);
    else if (t.dataset.down !== undefined) swap(+t.dataset.down, +t.dataset.down + 1);
    else if (t.dataset.rm !== undefined) { draft.order.splice(+t.dataset.rm, 1); render(); }
    else if (t.dataset.add !== undefined) { const v = rowEl.querySelector("[data-pick]").value; if (v) { draft.order.push(v); render(); } }
    else if (t.dataset.cancel !== undefined) { editing = null; draft = null; render(); }
    else if (t.dataset.reset !== undefined) save(id, null);
    else if (t.dataset.save !== undefined) {
      const mode = rowEl.querySelector(`input[name="mode-${id}"]:checked`);
      save(id, { role: rowEl.querySelector("[data-role]").value, order: draft.order, mode: draft.order.length ? (mode ? mode.value : "first") : "inherit" });
    }
  }

  async function onChange(e) {
    const ref = e.target.dataset && e.target.dataset.keep; if (ref === undefined) return;
    try {
      keep = await A.api("PUT", "/api/brains/keepalive", { changes: { [ref]: e.target.value || null } });
      A.toast(e.target.value ? "Il modello resterà in memoria per quel tempo dopo l'ultima risposta" : "Permanenza tornata predefinita");
    } catch (err) { A.toast(err.message, true); }
  }

  function init() {
    $("br-assign").addEventListener("click", onClick);
    $("br-assign").addEventListener("change", onChange);
  }

  A.brainAssign = { init, load };
})();
