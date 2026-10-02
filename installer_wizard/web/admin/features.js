(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  const MODE_LABEL = { auto: "Automatica", 1: "Sempre attiva", 0: "Disattivata" };
  let featCat = "all", featState = "all", fsetTimer = null;
  const find = (fid) => A.featData.features.find((x) => x.id === fid);

  function renderNav() {
    const pinned = A.featData.features.filter((f) => f.pinned);
    $("nav-pinned").innerHTML = pinned.map((f) => `<a data-tab="${fmt.esc(f.panel || "feature")}" data-feature="${fmt.esc(f.id)}"
        class="${A.currentFeature === f.id ? "on" : ""}" title="${fmt.esc(f.name)}"><span class="ic">${fmt.esc(f.icon)}</span><span class="lb">${fmt.esc(f.name)}</span>
        ${f.state.enabled ? "" : '<span class="off" title="disattivata"></span>'}</a>`).join("")
      || '<div class="empty">Aggiungi i preferiti con ☆ dalle Funzionalità</div>';
  }

  function modeSelect(f, attr) {
    if (!f.toggle) return '<span style="flex:1"></span>';
    return `<select ${attr}="${fmt.esc(f.id)}" title="Modalità">${["auto", "1", "0"].map((m) => `<option value="${m}" ${f.state.mode === m ? "selected" : ""}>${MODE_LABEL[m]}</option>`).join("")}</select>`;
  }

  const stateBadge = (f) => f.state.enabled ? `<span class="badge ${f.state.risk ? "warn" : "ok"}">attiva</span>` : '<span class="badge">spenta</span>';

  function renderFeatures() {
    const { featData } = A;
    const q = ($("feat-q").value || "").toLowerCase();
    const counts = {};
    featData.features.forEach((f) => { counts[f.category] = (counts[f.category] || 0) + 1; });
    $("feat-cats").innerHTML = [["all", "Tutte", featData.features.length], ...Object.entries(featData.categories).filter(([k]) => counts[k]).map(([k, v]) => [k, v, counts[k]])]
      .map(([k, v, n]) => `<button data-cat="${k}" class="${featCat === k ? "on" : ""}">${fmt.esc(v)}<small>${n}</small></button>`).join("");
    const list = featData.features.filter((f) => (featCat === "all" || f.category === featCat)
      && (featState === "all" || (featState === "on") === f.state.enabled)
      && (!q || JSON.stringify([f.name, f.description, f.capabilities]).toLowerCase().includes(q)));
    $("feat-grid").innerHTML = list.map((f) => `<div class="fcard ${f.state.enabled ? "on" : "off"}" data-fid="${fmt.esc(f.id)}">
        <div class="hd"><div class="ico">${fmt.esc(f.icon)}</div>
          <div style="flex:1; min-width:0"><div class="nm">${fmt.esc(f.name)} ${f.new ? '<span class="badge warn">nuova</span>' : ""}</div>
          <div class="ct">${fmt.esc(featData.categories[f.category] || "")}${f.source === "ai" ? " · creata da Jarvis" : f.source === "user" ? " · aggiunta da te" : ""}</div></div>
          <button class="pin ${f.pinned ? "on" : ""}" data-pin="${fmt.esc(f.id)}" title="${f.pinned ? "Togli dal menu laterale" : "Aggiungi al menu laterale"}">${f.pinned ? "★" : "☆"}</button></div>
        <div class="ds">${fmt.esc(f.description)}</div>
        <div class="st">${stateBadge(f)} <span>${fmt.esc(f.state.reason)}</span></div>
        <div class="ft">${modeSelect(f, "data-fmode")}<button class="btn sm" data-open="${fmt.esc(f.id)}">Apri</button></div></div>`).join("")
      || '<div class="faint">Nessuna funzionalità corrisponde alla ricerca.</div>';
    const hw = featData.hardware || {};
    $("feat-note").innerHTML = `Le funzionalità vengono scoperte da sole nelle cartelle <span class="mono">installer_wizard/features</span> e <span class="mono">${fmt.esc(featData.user_dir || "")}</span>: ogni nuova cartella con un <span class="mono">feature.json</span> compare qui entro 20 secondi.
      Hardware rilevato: ${hw.ram_gb || "?"} GB di RAM · ${hw.cores || "?"} core · ${hw.gpu ? `${fmt.esc(hw.gpu)} (${hw.vram_gb} GB)` : "nessuna GPU adatta"} · webcam ${hw.video ? "presente" : "assente"}.`
      + (featData.errors.length ? `<div style="color:var(--amber); margin-top:8px">Manifest non validi: ${featData.errors.map((e) => `${fmt.esc(e.path)} (${fmt.esc(e.error)})`).join("; ")}</div>` : "");
  }

  A.renderFeatureBar = () => {
    const f = A.currentFeature && find(A.currentFeature);
    const bar = $("fbar");
    if (!f || A.isOn("feature")) { bar.classList.remove("show"); return; }
    bar.classList.add("show");
    bar.innerHTML = `<span class="crumb" data-back="1">▦ Funzionalità ›</span><b>${fmt.esc(f.icon)} ${fmt.esc(f.name)}</b>${stateBadge(f)}
      <span class="why">${fmt.esc(f.state.reason)}</span>${f.settings.length ? `<button class="btn sm" data-fset="${fmt.esc(f.id)}">Impostazioni</button>` : ""}
      ${modeSelect(f, "data-fmode")}<button class="pin ${f.pinned ? "on" : ""}" data-bpin="1" title="Menu laterale">${f.pinned ? "★" : "☆"}</button>`;
  };

  function settingInput(st, v) {
    const a = `data-fk="${fmt.esc(st.key)}"`;
    if (st.type === "select") return `<select ${a}>${(st.options || []).map((o) => { const val = typeof o === "object" ? o.value : o, lab = typeof o === "object" ? o.label : o;
      return `<option value="${fmt.esc(val)}" ${String(val) === String(v) ? "selected" : ""}>${fmt.esc(lab || "—")}</option>`; }).join("")}</select>`;
    if (st.type === "bool") return `<label class="switch"><input type="checkbox" ${a} ${v === "1" || v === true ? "checked" : ""}> ${fmt.esc(st.label)}</label>`;
    if (st.type === "color") return `<input ${a} type="color" value="${fmt.esc(v || "#000000")}" style="height:40px; padding:4px">`;
    return `<input ${a} type="${st.type === "secret" ? "password" : st.type === "number" ? "number" : "text"}" step="any" value="${fmt.esc(v)}" placeholder="${fmt.esc(st.placeholder || (st.type === "secret" ? "non impostata" : ""))}" autocomplete="off">`;
  }

  function renderFeaturePage(f) {
    $("feature-page").innerHTML = `<div class="row" style="gap:14px; flex-wrap:wrap; margin-bottom:10px">
        <span class="crumb faint" style="cursor:pointer" data-back="1">▦ Funzionalità ›</span></div>
      <div class="hd row" style="gap:14px; align-items:flex-start; flex-wrap:wrap">
        <div class="ico" style="width:54px;height:54px;border-radius:14px;display:grid;place-items:center;font-size:26px;border:1px solid var(--line-strong);background:rgba(41,224,255,0.08)">${fmt.esc(f.icon)}</div>
        <div style="flex:1; min-width:220px"><h2 style="margin:0; font-weight:400">${fmt.esc(f.name)}</h2>
          <div class="dim" style="font-size:13px; margin-top:4px">${fmt.esc(f.description)}</div>
          <div class="st" style="margin-top:8px; font-size:12px">${stateBadge(f)} <span class="faint">${fmt.esc(f.state.reason)}</span></div></div>
        <div class="row">${modeSelect(f, "data-fmode")}<button class="pin ${f.pinned ? "on" : ""}" data-ppin="1" title="Menu laterale">${f.pinned ? "★" : "☆"}</button></div></div>
      ${f.capabilities.length ? `<div class="panel-title" style="margin-top:20px">Cosa sa fare</div><div class="caps">${f.capabilities.map((c) => `<span>${fmt.esc(c)}</span>`).join("")}</div>` : ""}
      ${f.settings.length ? `<div class="panel-title" style="margin-top:22px">Impostazioni <span class="saved" id="f-saved">✓ salvato</span></div>
        <div class="form-grid">${f.settings.map((st) => st.type === "bool" ? `<div>${settingInput(st, f.values[st.key])}</div>`
          : `<div><label>${fmt.esc(st.label)}</label>${settingInput(st, f.values[st.key])}</div>`).join("")}</div>` : ""}
      ${f.panel ? `<div class="actions" style="margin-top:20px"><button class="btn primary" data-fpanel="${fmt.esc(f.panel)}">Apri il pannello completo</button></div>` : ""}`;
  }

  function saveFeatureSetting(el) {
    const fid = A.currentFeature; if (!fid) return;
    const value = el.type === "checkbox" ? (el.checked ? "1" : "0") : el.value;
    clearTimeout(fsetTimer);
    fsetTimer = setTimeout(async () => {
      try { const r = await A.api("PUT", `/api/features/${encodeURIComponent(fid)}/settings`, { [el.dataset.fk]: value });
        const f = find(fid); if (f) f.values = r.values;
        A.flash("f-saved");
        if (r.applying && r.applying.length) A.toast("Salvato: applicazione in corso"); }
      catch (e) { A.toast(e.message, true); }
    }, el.type === "checkbox" || el.tagName === "SELECT" || el.type === "color" ? 0 : 800);
  }

  function refresh() { renderNav(); renderFeatures(); A.renderFeatureBar(); }

  async function updateFeature(fid, body) {
    try { A.featData = await A.api("PUT", `/api/features/${encodeURIComponent(fid)}`, body); refresh(); }
    catch (e) { A.toast(e.message, true); }
  }

  A.loadFeatures = async () => {
    try { A.featData = await A.api("GET", "/api/features"); } catch (e) { return; }
    refresh();
    const f = A.currentFeature && find(A.currentFeature);
    if (f && A.isOn("feature") && !$("feature-page").contains(document.activeElement)) renderFeaturePage(f);
  };

  A.openFeature = (fid) => {
    const f = find(fid);
    if (!f) return A.openTab("features");
    A.openTab(f.panel || "feature", fid);
  };

  function init() {
    $("feat-q").addEventListener("input", renderFeatures);
    $("feat-cats").addEventListener("click", (e) => { const b = e.target.closest("[data-cat]"); if (b) { featCat = b.dataset.cat; renderFeatures(); } });
    $("feat-state").addEventListener("click", (e) => { const b = e.target.closest("[data-st]"); if (!b) return; featState = b.dataset.st;
      $("feat-state").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b)); renderFeatures(); });
    $("feat-rescan").addEventListener("click", async () => { try { A.featData = await A.api("POST", "/api/features/rescan"); renderNav(); renderFeatures(); A.toast("Cartelle e hardware riletti"); } catch (e) { A.toast(e.message, true); } });
    $("feat-grid").addEventListener("click", (e) => {
      const pin = e.target.closest("[data-pin]"); if (pin) { const f = find(pin.dataset.pin); updateFeature(f.id, { pinned: !f.pinned }); return; }
      const op = e.target.closest("[data-open]"); if (op) A.openFeature(op.dataset.open);
    });
    document.addEventListener("change", (e) => {
      const fid = e.target.dataset.fmode; if (!fid) return;
      const f = find(fid);
      if (e.target.value === "1" && f && f.state.mode !== "1" && !f.state.enabled && !confirm(`${f.name}: ${f.state.reason}.\nAttivarla comunque? Potrebbe rallentare il sistema.`)) { e.target.value = f.state.mode; return; }
      updateFeature(fid, { mode: e.target.value }).then(() => A.toast(`${f.name}: ${MODE_LABEL[e.target.value].toLowerCase()}`));
    });
    $("fbar").addEventListener("click", (e) => {
      if (e.target.closest("[data-back]")) return A.openTab("features");
      if (e.target.closest("[data-bpin]")) { const f = find(A.currentFeature); return updateFeature(f.id, { pinned: !f.pinned }); }
      const st = e.target.closest("[data-fset]"); if (st) A.openTab("feature", st.dataset.fset);
    });
    $("feature-page").addEventListener("input", (e) => { if (e.target.dataset.fk && e.target.type !== "checkbox" && e.target.tagName !== "SELECT") saveFeatureSetting(e.target); });
    $("feature-page").addEventListener("change", (e) => { if (e.target.dataset.fk && (e.target.type === "checkbox" || e.target.tagName === "SELECT")) saveFeatureSetting(e.target); });
    $("feature-page").addEventListener("click", (e) => {
      if (e.target.closest("[data-back]")) return A.openTab("features");
      if (e.target.closest("[data-ppin]")) { const f = find(A.currentFeature); updateFeature(f.id, { pinned: !f.pinned }).then(() => renderFeaturePage(find(f.id))); return; }
      const p = e.target.closest("[data-fpanel]"); if (p) A.openTab(p.dataset.fpanel, A.currentFeature);
    });
  }

  A.tab("features", { title: "Funzionalità", init, load: A.loadFeatures,
    onState(s) { if (s.features_rev && s.features_rev !== window.__featRev) { window.__featRev = s.features_rev; A.loadFeatures(); } } });
  A.tab("feature", { title: "Funzionalità", load: (f) => { if (f) renderFeaturePage(f); } });
})();
