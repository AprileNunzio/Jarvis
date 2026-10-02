(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  let data = null;

  const pct = (v) => Math.round((v || 0) * 100);
  const bar = (label, v) => `<div class="mn-score"><span>${label}</span>
    <div class="mn-track"><i style="width:${pct(v)}%"></i></div><b>${pct(v)}%</b></div>`;

  const KINDS = { fatto: "fatto", identita: "identità", preferenza: "preferenza", lavoro: "lavoro",
    luogo: "luogo", relazione: "relazione", abitudine: "abitudine", obiettivo: "obiettivo" };

  function factRow(f) {
    return `<div class="cat-item"><div style="flex:1">
      <div class="nm">${fmt.esc(f.text)}</div>
      <div class="nt">${fmt.esc(KINDS[f.kind] || f.kind)}${f.who ? ` · ${fmt.esc(f.who)}` : ""} · forza ${pct(f.score)}%${f.hits ? ` · usato ${f.hits}×` : ""}</div>
    </div><button class="btn sm" data-forget="${fmt.esc(f.id)}" title="Dimentica">✕</button></div>`;
  }

  function diaryRow(e) {
    const when = new Date(e.at * 1000).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });
    const tags = [];
    tags.push(`<span class="badge ${e.memory === "lungo" ? "warn" : ""}">memoria ${fmt.esc(e.memory)}</span>`);
    if (e.study) tags.push('<span class="badge">studio</span>');
    if (e.widget) tags.push(`<span class="badge">vista ${fmt.esc(e.widget)}</span>`);
    if (!e.directed) tags.push('<span class="badge">non per me</span>');
    return `<div class="mn-entry">
      <div class="mn-head"><span class="mn-said">« ${fmt.esc(e.said)} »</span><span class="faint">${when}</span></div>
      <div class="mn-tags">${tags.join(" ")} <span class="faint">fiducia ${pct(e.confidence)}%</span></div>
      <div class="mn-bars">${bar("pertinenza", e.scores.relevance)}${bar("importanza", e.scores.importance)}${bar("memorabilità", e.scores.memorability)}</div>
      ${e.facts && e.facts.length ? `<div class="mn-learned">↳ ricordato: ${e.facts.map((x) => fmt.esc(x)).join("; ")}</div>` : ""}
      <div class="faint" style="font-size:12px">${fmt.esc(e.note)}</div></div>`;
  }

  async function load() {
    try { data = await A.api("GET", "/api/mind"); } catch (e) { A.toast(e.message, true); return; }
    $("mn-long").checked = !!data.settings.long_term;
    $("mn-llm").checked = !!data.settings.llm_facts;
    $("mn-study").checked = !!data.settings.study_feed;
    const thr = data.settings.min_memorability != null ? data.settings.min_memorability : 0.5;
    $("mn-thr").value = thr; $("mn-thr-v").textContent = `${pct(thr)}%`;
    const c = data.counters;
    $("mn-stats").innerHTML = `<span><b>${data.facts_stats.count}</b> ricordi a lungo termine</span>
      <span><b>${c.evaluated}</b> frasi valutate</span><span><b>${c.stored}</b> memorizzate</span><span><b>${c.study}</b> spunti di studio</span>`;
    $("mn-note").textContent = data.enabled ? "" : "Mente disattivata (Funzionalità → Mente).";
    $("mn-suggest").innerHTML = (data.suggestions || []).map((s) =>
      `<div class="mn-sugg">💡 ${fmt.esc(s.text)} <button class="btn sm" data-sugg="${fmt.esc(s.id)}">Ok, ho capito</button></div>`).join("");
    $("mn-facts").innerHTML = data.facts.length ? data.facts.map(factRow).join("")
      : '<div class="faint">Ancora nessun ricordo. Parla con Jarvis di te: imparerà i fatti che contano.</div>';
    $("mn-diary").innerHTML = data.diary.length ? data.diary.map(diaryRow).join("")
      : '<div class="faint">Il diario si riempirà dopo i primi scambi.</div>';
  }

  async function saveSettings() {
    try {
      await A.api("PUT", "/api/mind", { long_term: $("mn-long").checked, llm_facts: $("mn-llm").checked,
        study_feed: $("mn-study").checked, min_memorability: parseFloat($("mn-thr").value) });
      load();
    } catch (e) { A.toast(e.message, true); }
  }

  function init() {
    $("mn-long").addEventListener("change", saveSettings);
    $("mn-llm").addEventListener("change", saveSettings);
    $("mn-study").addEventListener("change", saveSettings);
    $("mn-thr").addEventListener("input", () => { $("mn-thr-v").textContent = `${pct(parseFloat($("mn-thr").value))}%`; });
    $("mn-thr").addEventListener("change", saveSettings);
    $("mn-facts").addEventListener("click", async (e) => {
      const el = e.target.closest("[data-forget]"); if (!el) return;
      try { await A.api("DELETE", `/api/mind/facts/${encodeURIComponent(el.dataset.forget)}`); load(); }
      catch (err) { A.toast(err.message, true); }
    });
    $("mn-suggest").addEventListener("click", async (e) => {
      const el = e.target.closest("[data-sugg]"); if (!el) return;
      try { await A.api("DELETE", `/api/mind/suggestions/${encodeURIComponent(el.dataset.sugg)}`); load(); }
      catch (err) { A.toast(err.message, true); }
    });
    $("mn-clear").addEventListener("click", async () => {
      if (!confirm("Svuotare tutta la memoria a lungo termine?")) return;
      try { const r = await A.api("POST", "/api/mind/clear"); A.toast(`Dimenticati ${r.removed} ricordi`); load(); }
      catch (err) { A.toast(err.message, true); }
    });
  }

  A.tab("mind", { title: "Mente", init, load });
})();
