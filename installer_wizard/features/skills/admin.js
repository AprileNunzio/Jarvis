(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  let skillData = null, skillSel = null;

  const skillItem = (k) => `
      <div class="cat-item" style="cursor:pointer; ${k.key === skillSel ? "border-color:var(--cyan)" : ""}" data-sk="${fmt.esc(k.key)}"><div>
        <div class="nm">${fmt.esc(k.name)} ${k.source === "ai" ? '<span class="badge warn">scritto da Jarvis</span>' : k.source === "user" ? '<span class="badge">tuo</span>' : ""} ${k.stats.enabled === false ? '<span class="badge">disattivato</span>' : ""}</div>
        <div class="nt">${fmt.esc(k.description)}</div>
        <div class="fit ok">${k.stats.uses || 0} usi${k.stats.uses ? ` · ~${k.stats.avg_ms} ms` : ""}${k.stats.fails ? ` · ${k.stats.fails} scarti` : ""}</div></div></div>`;

  async function loadSkills() {
    try { skillData = await A.api("GET", "/api/skills"); } catch (e) { A.toast(e.message, true); return; }
    const byCat = {};
    skillData.skills.forEach((k) => (byCat[k.category_label] = byCat[k.category_label] || []).push(k));
    $("sk-list").innerHTML = Object.entries(byCat).map(([cat, list]) => `<div class="panel-title" style="margin:6px 0 2px">${fmt.esc(cat)}</div>` + list.map(skillItem).join("")).join("")
      || '<div class="faint">Nessun algoritmo.</div>';
    $("sk-note").innerHTML = `${skillData.generate ? "Quando manca un algoritmo, Jarvis risponde subito e intanto ne scrive uno nuovo, lo controlla e lo prova in un processo isolato." : "Creazione automatica disattivata (Funzionalità → Algoritmi)."} Cartella: <span class="mono">${fmt.esc(skillData.user_dir)}</span>`
      + (skillData.errors.length ? `<div style="color:var(--amber)">Scartati: ${skillData.errors.map((e) => `${fmt.esc(e.path)} (${fmt.esc(e.error)})`).join("; ")}</div>` : "");
    if (skillSel) openSkill(skillSel);
  }

  async function openSkill(key) {
    skillSel = key;
    const k = skillData.skills.find((x) => x.key === key); if (!k) return;
    let code = "";
    try { code = await fetch(`/api/skills/${key}/code`, { credentials: "same-origin" }).then((r) => r.text()); } catch (e) {}
    $("sk-detail").innerHTML = `<div class="row" style="justify-content:space-between; flex-wrap:wrap"><h2 style="margin:0; font-weight:400">${fmt.esc(k.name)}</h2>
        <div class="actions"><label class="switch"><input type="checkbox" id="sk-on" ${k.stats.enabled !== false ? "checked" : ""}> attivo</label>
        ${k.source !== "system" ? '<button class="btn sm danger" id="sk-del">Elimina</button>' : ""}</div></div>
      <div class="faint mono" style="font-size:11px; margin:4px 0 10px">${fmt.esc(k.key)}${k.created_at ? ` · creato ${new Date(k.created_at * 1000).toLocaleString("it-IT")}` : ""}</div>
      <div class="dim" style="font-size:13px">${fmt.esc(k.description)}</div>
      ${k.examples.length ? `<div class="caps" style="margin-top:10px">${k.examples.map((x) => `<span>${fmt.esc(x)}</span>`).join("")}</div>` : ""}
      <form class="route-box" id="sk-try" style="margin-top:14px"><input id="sk-try-q" placeholder="Prova solo questo algoritmo"><button class="btn">Esegui</button></form>
      <div class="route-res" id="sk-try-res"></div>
      <div class="panel-title" style="margin-top:14px">Si attiva con</div><pre class="log" style="height:auto">${fmt.esc(k.patterns.join("\n"))}</pre>
      <div class="panel-title" style="margin-top:14px">Codice</div><pre class="log" style="height:auto; max-height:46vh">${fmt.esc(code)}</pre>`;
  }

  function init() {
    $("sk-list").addEventListener("click", (e) => { const el = e.target.closest("[data-sk]"); if (el) { openSkill(el.dataset.sk); document.querySelectorAll("#sk-list [data-sk]").forEach((x) => x.style.borderColor = x === el ? "var(--cyan)" : ""); } });
    $("sk-detail").addEventListener("change", async (e) => {
      if (e.target.id !== "sk-on") return;
      try { await A.api("PUT", `/api/skills/${skillSel}`, { enabled: e.target.checked }); loadSkills(); } catch (err) { A.toast(err.message, true); }
    });
    $("sk-detail").addEventListener("click", async (e) => {
      if (e.target.id !== "sk-del" || !confirm("Eliminare questo algoritmo?")) return;
      try { await A.api("DELETE", `/api/skills/${skillSel}`); skillSel = null; $("sk-detail").innerHTML = '<div class="faint">Algoritmo eliminato.</div>'; loadSkills(); } catch (err) { A.toast(err.message, true); }
    });
    $("sk-detail").addEventListener("submit", async (e) => {
      e.preventDefault(); const text = $("sk-try-q").value.trim(); if (!text) return;
      try { const r = await A.api("POST", `/api/skills/${skillSel}/test`, { text });
        $("sk-try-res").innerHTML = r.ok ? `✓ ${fmt.esc(r.speech || r.result)} <span class="faint">· ${r.total_ms} ms${r.matches ? "" : " · (la frase non attiverebbe da sola questo algoritmo)"}</span>` : `<span style="color:var(--amber)">✕ ${fmt.esc(r.error || "nessun risultato")}</span>`; }
      catch (err) { A.toast(err.message, true); }
    });
    $("sk-ask").addEventListener("submit", async (e) => {
      e.preventDefault(); const text = $("sk-q").value.trim(); if (!text) return;
      try { const r = await A.api("POST", "/api/skills/ask", { text }), a = r.answer;
        $("sk-res").innerHTML = a ? `∑ <b>${fmt.esc(a.name)}</b>: ${fmt.esc(a.speech)} <span class="faint">· ${a.total_ms} ms</span>`
          : `<span class="faint">Nessun algoritmo: risponderebbe il modello linguistico${r.needs ? " e Jarvis ne scriverebbe uno nuovo per la prossima volta" : ""}.</span>`; }
      catch (err) { A.toast(err.message, true); }
    });
  }

  A.tab("skills", { title: "Algoritmi", init, load: loadSkills });
})();
