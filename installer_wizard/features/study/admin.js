(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  const ST_STATE = { studying: "🎓 Sta studiando", waiting: "⏸ In attesa", paused: "⏸ In pausa", idle: "✓ In pari",
                     off: "○ Disattivato", budget: "⏹ Tempo esaurito", hours: "☾ Fuori orario" };
  const SOURCE_LBL = { manual: "scelta da te", auto: "dalle conversazioni" };
  const STATUS_LBL = { active: ["ok", "in studio"], paused: ["", "in pausa"], proposed: ["warn", "proposta"], done: ["done", "completata"] };
  const SETTINGS_UI = [
    ["enabled", "bool", "Studio autonomo attivo"],
    ["use_in_answers", "bool", "Usa ciò che ha studiato nelle risposte"],
    ["auto_discover", "bool", "Scopri le materie dalle conversazioni"],
    ["auto_accept", "bool", "Studia subito le materie scoperte (altrimenti restano proposte)"],
    ["web_sources", "bool", "Studia su fonti reali (Wikipedia italiana e inglese)"],
    ["idle_minutes", "number", "Minuti di inattività prima di studiare"],
    ["max_cpu", "number", "Non iniziare se la CPU supera (%)"],
    ["daily_minutes", "number", "Tempo massimo di studio al giorno (minuti)"],
    ["hours_from", "time", "Studia solo dalle (vuoto = sempre)"],
    ["hours_to", "time", "…alle"],
    ["min_mentions", "number", "Conversazioni per proporre una materia"],
    ["lessons_per_level", "number", "Lezioni per livello"],
    ["depth", "select:breve,normale,approfondita", "Profondità degli appunti"],
    ["model", "text", "Modello di studio (vuoto = principale)"],
  ];
  const pct = (x) => `${Math.round((x || 0) * 100)}%`;
  let studyData = null, studySel = null, studySettingsTimer = null;

  function renderHead(d) {
    const st = d.status || {};
    $("st-state").textContent = ST_STATE[st.state] || st.state || "—";
    $("st-detail").textContent = st.topic ? `${st.topic} · ${st.level} — ${st.detail}` : (st.detail || "");
    $("st-cells").textContent = d.memory.cells.toLocaleString("it-IT");
    const ls = d.memory.last_search || {};
    $("st-mem").textContent = `binario ${fmt.bytes(d.memory.binary_bytes)} · ternario ${fmt.bytes(d.memory.ternary_bytes)}${ls.total_ms != null ? ` · ricerca ${ls.total_ms} ms` : ""}`;
    $("st-time").textContent = `${Math.round(d.stats.seconds_today / 60)} min`;
    $("st-time2").textContent = `oggi su ${d.settings.daily_minutes} · totale ${(d.stats.seconds_total / 3600).toFixed(1)} h`;
    $("st-tasks").textContent = d.stats.lessons;
    $("st-tasks2").textContent = `lezioni · ${d.stats.reviews} ripassi · ${d.stats.exams} esami · ${d.stats.queue} domande da analizzare`;
    if (!$("st-target").options.length) $("st-target").innerHTML = Object.entries(d.levels).map(([n, l]) => `<option value="${n}" ${n === "4" ? "selected" : ""}>${n} · ${l}</option>`).join("");
  }

  async function loadStudy() {
    try { studyData = await A.api("GET", "/api/study"); } catch (e) { A.toast(e.message, true); return; }
    const d = studyData;
    renderHead(d);
    renderTopics(); renderStudySettings(); A.renderSoup(d.soup);
    $("st-journal").innerHTML = d.journal.map((j) => `<div><span class="faint mono">${new Date(j.at * 1000).toLocaleString("it-IT", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</span> ${fmt.esc(j.text)}</div>`).join("") || '<div class="faint">Ancora nessuna attività.</div>';
    if (studySel) openTopic(studySel, true);
  }

  function levelBars(t) {
    return `<div class="levels">${t.levels_detail.map((l) => `<div class="${l.level > t.target_level ? "beyond" : ""}" title="${l.done}/${l.lessons} lezioni${l.mastery != null ? ` · padronanza ${pct(l.mastery)}` : ""}">
      <div class="lb"><i style="width:${pct(l.progress)}"></i></div>${l.level}. ${fmt.esc(l.name)} ${l.progress ? pct(l.progress) : ""}</div>`).join("")}</div>`;
  }

  function renderTopics() {
    const d = studyData;
    $("st-topics").innerHTML = d.topics.map((t) => {
      const [cls, lbl] = STATUS_LBL[t.status] || ["", t.status];
      return `<div class="topic ${t.id === studySel ? "on" : ""}" data-topic="${fmt.esc(t.id)}">
        <div class="hd"><span class="nm">${fmt.esc(t.name)}</span><span class="badge ${cls}">${lbl}</span>
          <span class="badge">${SOURCE_LBL[t.source] || t.source}</span><b class="mono">${pct(t.progress)}</b></div>
        <div class="faint" style="font-size:12px; margin-top:4px">Livello attuale: ${fmt.esc(t.level_name)} · obiettivo ${fmt.esc(d.levels[t.target_level])} · priorità ${t.priority}
          · ${t.cells} celle${t.due_reviews ? ` · ${t.due_reviews} ripassi in scadenza` : ""}${t.mentions ? ` · citata ${t.mentions} volte` : ""}</div>
        ${levelBars(t)}</div>`;
    }).join("") || '<div class="faint">Nessuna materia: aggiungine una qui sopra oppure parla con Jarvis dei tuoi interessi, le scoprirà da solo.</div>';
    $("st-mentions").innerHTML = d.mentions.length ? `<div class="panel-title">Interessi emersi dalle conversazioni</div>` + d.mentions.map((m) => `<div class="row" style="justify-content:space-between; padding:6px 0">
        <span>${fmt.esc(m.name)} <span class="faint" style="font-size:12px">· ${m.count} ${m.count === 1 ? "volta" : "volte"}${m.hints && m.hints.length ? ` · ${fmt.esc(m.hints.slice(0, 3).join(", "))}` : ""}</span></span>
        <span class="actions"><button class="btn sm" data-mention="${fmt.esc(m.key)}">Studia</button><button class="btn sm danger" data-mention-drop="${fmt.esc(m.key)}">Ignora</button></span></div>`).join("") : "";
  }

  function lessonHtml(l) {
    const scored = (l.questions || []).filter((q) => q.last_score != null);
    return `<div class="lesson"><span>${l.status === "done" ? "✅" : l.retry ? "🔁" : "○"}</span><span>${fmt.esc(l.title)}</span>
          <span class="faint mono">${scored.length ? pct(scored.reduce((a, q) => a + q.last_score, 0) / scored.length) : ""}</span>
          ${l.summary ? `<details><summary>Appunti${l.sources && l.sources.length ? ` · ${l.sources.length} fonti` : ""}</summary><p>${fmt.esc(l.summary)}</p>
            <ul>${(l.facts || []).map((f) => `<li>${fmt.esc(f)}</li>`).join("")}</ul>
            ${(l.exercises || []).length ? `<div class="st-ex"><b>Esercizi</b>${l.exercises.map((e) => `<div style="margin-top:6px"><b>Es:</b> ${fmt.esc(e.q)}<br><b>Soluzione:</b> ${fmt.esc(e.a)}</div>`).join("")}</div>` : ""}
            ${(l.sources || []).map((s) => `<a href="${fmt.esc(s.url)}" target="_blank" rel="noopener" style="color:var(--cyan)">${fmt.esc(s.title)}</a>`).join(" · ")}
            ${(l.questions || []).map((q) => `<div style="margin-top:6px"><b>D:</b> ${fmt.esc(q.q)}<br><b>R:</b> ${fmt.esc(q.a)} <span class="faint">${q.history && q.history.length ? `(voti: ${q.history.map((x) => Math.round(x * 100)).join(", ")})` : ""}</span></div>`).join("")}
          </details>` : ""}</div>`;
  }

  async function openTopic(id, quiet) {
    studySel = id;
    let t;
    try { t = await A.api("GET", `/api/study/topics/${encodeURIComponent(id)}`); } catch (e) { if (!quiet) A.toast(e.message, true); return; }
    document.querySelectorAll(".topic").forEach((x) => x.classList.toggle("on", x.dataset.topic === id));
    const p = $("st-detail-panel"); p.style.display = "block";
    if (p.contains(document.activeElement) && quiet) return;
    const levels = Object.entries(t.levels).sort((a, b) => a[0] - b[0]);
    p.innerHTML = `<div class="row" style="justify-content:space-between; flex-wrap:wrap"><h2 style="margin:0; font-weight:400">${fmt.esc(t.name)}</h2>
        <div class="actions">
          <button class="btn sm" data-tact="${t.status === "paused" ? "resume" : "pause"}">${t.status === "paused" ? "▶ Riprendi" : "⏸ Pausa"}</button>
          <button class="btn sm" data-tact="reset">↺ Ricomincia</button>
          <button class="btn sm danger" data-tact="delete">Elimina</button></div></div>
      ${levelBars(t)}
      <div class="form-grid" style="margin-top:16px">
        <div><label>Obiettivo</label><select data-tk="target_level">${Object.entries(studyData.levels).map(([n, l]) => `<option value="${n}" ${+n === t.target_level ? "selected" : ""}>${n} · ${l}</option>`).join("")}</select></div>
        <div><label>Priorità</label><select data-tk="priority">${[1, 2, 3, 4, 5].map((n) => `<option ${n === t.priority ? "selected" : ""}>${n}</option>`).join("")}</select></div>
        <div class="wide"><label>Preferenze e taglio dello studio</label><input data-tk="focus" value="${fmt.esc(t.focus || "")}" placeholder="es. più pratica che teoria, orientato alle riparazioni"></div>
      </div>
      ${t.hints && t.hints.length ? `<div class="muted-note">Argomenti citati nelle conversazioni: ${fmt.esc(t.hints.join(", "))}</div>` : ""}
      ${levels.map(([n, lv]) => `<div class="panel-title" style="margin-top:20px">Livello ${n} · ${fmt.esc(studyData.levels[n])}
          ${lv.exams && lv.exams.length ? ` — esami: ${lv.exams.map((e) => pct(e.score)).join(", ")}` : ""}${lv.passed_at ? " ✓ superato" : ""}</div>
        ${lv.lessons.map(lessonHtml).join("")}`).join("") || '<div class="muted-note">Il programma del primo livello verrà preparato al prossimo momento di riposo.</div>'}`;
  }

  function renderStudySettings() {
    if ($("st-settings").contains(document.activeElement)) return;
    const s = studyData.settings;
    $("st-settings").innerHTML = SETTINGS_UI.map(([k, type, label]) => {
      if (type === "bool") return `<div><label class="switch"><input type="checkbox" data-sk="${k}" ${s[k] ? "checked" : ""}> ${label}</label></div>`;
      if (type.startsWith("select:")) return `<div><label>${label}</label><select data-sk="${k}">${type.slice(7).split(",").map((o) => `<option ${o === s[k] ? "selected" : ""}>${o}</option>`).join("")}</select></div>`;
      return `<div><label>${label}</label><input data-sk="${k}" type="${type}" value="${fmt.esc(s[k])}" ${k === "model" ? `placeholder="${fmt.esc(studyData.model)}"` : ""}></div>`;
    }).join("");
  }

  function saveStudySetting(el) {
    const k = el.dataset.sk, v = el.type === "checkbox" ? el.checked : el.value;
    clearTimeout(studySettingsTimer);
    studySettingsTimer = setTimeout(async () => {
      try { studyData.settings = await A.api("PUT", "/api/study/settings", { [k]: v }); A.flash("st-saved"); }
      catch (e) { A.toast(e.message, true); }
    }, el.type === "checkbox" || el.tagName === "SELECT" ? 0 : 700);
  }

  async function topicAction(a) {
    const url = `/api/study/topics/${encodeURIComponent(studySel)}`;
    if (a === "delete") {
      if (!confirm("Eliminare la materia con tutto ciò che Jarvis ha imparato?")) return false;
      await A.api("DELETE", url); studySel = null; $("st-detail-panel").style.display = "none";
    } else if (a === "reset") {
      if (!confirm("Ricominciare la materia dal livello base? La memoria di questa materia verrà cancellata.")) return false;
      await A.api("POST", `${url}/reset`);
    } else await A.api("PUT", url, { status: a === "pause" ? "paused" : "active" });
    return true;
  }

  async function search(e) {
    e.preventDefault(); const q = $("st-q").value.trim(); if (!q) return;
    try {
      const r = await A.api("POST", "/api/study/search", { q });
      const t = r.timing || {};
      $("st-timing").textContent = `${t.cells || 0} celle · binario+ternario ${t.binary_ternary_ms ?? "—"} ms · coseno esatto ${t.exact_ms ?? "—"} ms · totale ${t.total_ms ?? "—"} ms`;
      $("st-hits").innerHTML = r.results.map((h) => `<div class="hit"><span class="sc">${h.score.toFixed(3)}</span> <span class="faint">${fmt.esc(h.topic_name || "")} · liv. ${h.level || "—"} · ${fmt.esc(h.kind || "")}${h.strength > 1 ? ` · rinforzata ×${h.strength}` : ""}</span><div>${fmt.esc(h.text)}</div></div>`).join("") || '<div class="faint">Nessun ricordo pertinente.</div>';
    } catch (err) { A.toast(err.message, true); }
  }

  function init() {
    $("st-settings").addEventListener("input", (e) => { if (e.target.dataset.sk && e.target.type !== "checkbox") saveStudySetting(e.target); });
    $("st-settings").addEventListener("change", (e) => { if (e.target.dataset.sk) saveStudySetting(e.target); });
    $("st-add").addEventListener("submit", async (e) => {
      e.preventDefault(); const name = $("st-name").value.trim(); if (!name) return;
      try {
        const t = await A.api("POST", "/api/study/topics", { name, target_level: +$("st-target").value, priority: +$("st-prio").value, focus: $("st-focus").value });
        $("st-name").value = ""; $("st-focus").value = ""; A.toast(`«${t.name}» aggiunta: la studierà al prossimo momento di riposo`); studySel = t.id; loadStudy();
      } catch (err) { A.toast(err.message, true); }
    });
    $("st-topics").addEventListener("click", (e) => { const el = e.target.closest(".topic"); if (el) openTopic(el.dataset.topic); });
    $("st-mentions").addEventListener("click", async (e) => {
      const k = e.target.dataset.mention, drop = e.target.dataset.mentionDrop;
      try {
        if (k) { await A.api("POST", `/api/study/mentions/${encodeURIComponent(k)}`); A.toast("Materia aggiunta"); }
        else if (drop) await A.api("DELETE", `/api/study/mentions/${encodeURIComponent(drop)}`);
        else return;
        loadStudy();
      } catch (err) { A.toast(err.message, true); }
    });
    $("st-detail-panel").addEventListener("change", async (e) => {
      const k = e.target.dataset.tk; if (!k || !studySel) return;
      try { await A.api("PUT", `/api/study/topics/${encodeURIComponent(studySel)}`, { [k]: e.target.value }); A.toast("Salvato"); loadStudy(); }
      catch (err) { A.toast(err.message, true); }
    });
    $("st-detail-panel").addEventListener("click", async (e) => {
      const a = e.target.dataset.tact; if (!a || !studySel) return;
      try { if (await topicAction(a)) loadStudy(); } catch (err) { A.toast(err.message, true); }
    });
    $("st-now").addEventListener("click", async () => { try { await A.api("POST", "/api/study/now"); A.toast("Jarvis inizia a studiare (si ferma se gli parli)"); } catch (e) { A.toast(e.message, true); } });
    $("st-search").addEventListener("submit", search);
  }

  function onState(s) {
    const sig = JSON.stringify(s.study || {});
    if (sig !== window.__studySig) { window.__studySig = sig; if (A.isOn("study")) loadStudy(); }
  }

  A.tab("study", { title: "Studio", init, load: loadStudy, onState });
})();
