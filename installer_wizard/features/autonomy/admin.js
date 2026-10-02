(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  const ICON = { routine: "⏰", diagnosi: "🩺", studio: "📚", approvazione: "🔐" };
  const when = (t) => (t ? new Date(t * 1000).toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" }) : "mai");
  let timer = null;

  function render(d) {
    $("au-status").textContent = `${d.enabled ? "Attiva" : "Disattivata"} · ${d.status} · ultimo giro dell'autopilota: ${when(d.last_autopilot)}`;
    const ap = $("au-approvals");
    ap.hidden = !d.approvals.length;
    ap.innerHTML = `<div class="panel-title">🔐 Aspettano la tua approvazione (${d.approvals.length})</div>` + d.approvals.map((a) =>
      `<div class="au-item" data-ap="${fmt.esc(a.id)}"><div><b>${fmt.esc(a.title)}</b><div>${fmt.esc(a.summary)}</div>
        <div class="faint">${when(a.at)}</div></div><div class="actions"><button class="btn sm primary" data-yes>Approva</button>${a.routine ? '<button class="btn sm" data-always>Approva sempre</button>' : ""}
        <button class="btn sm danger" data-no>Rifiuta</button></div></div>`).join("");
    $("au-list").innerHTML = d.routines.map((r) => `<div class="au-item ${r.enabled ? "" : "off"}" data-r="${fmt.esc(r.id)}">
        <div><b>${fmt.esc(r.title)}</b> <span class="badge">${fmt.esc(r.when_text)}</span>${r.trusted ? ' <span class="badge ok" title="Esegue anche email e azioni delicate senza chiedere">autorizzato</span>' : ""}
          <div class="faint">${fmt.esc(r.prompt)}</div>
          <div class="faint">Eseguito ${r.runs || 0} volte · ultima: ${when(r.last_run)}${r.last_result ? ` — ${fmt.esc(r.last_result)}` : ""}</div></div>
        <div class="actions"><button class="btn sm" data-run>Esegui ora</button>
          ${r.trusted ? '<button class="btn sm" data-untrust>Revoca autorizzazione</button>' : ""}<button class="btn sm" data-toggle>${r.enabled ? "Sospendi" : "Riattiva"}</button><button class="btn sm danger" data-del>Elimina</button></div></div>`).join("")
      || '<div class="faint">Nessun compito. Aggiungine uno qui sopra o di\' a Jarvis: «ogni mattina alle 8 mandami il meteo per email».</div>';
    $("au-journal").innerHTML = d.journal.map((e) => `<div class="au-log"><span>${ICON[e.kind] || "•"}</span>
        <div><b>${fmt.esc(e.title)}</b> <span class="faint">${when(e.at)}</span><div>${fmt.esc(e.text)}</div>
        ${e.steps && e.steps.length ? `<div class="faint mono">${e.steps.map((s) => fmt.esc(s.tool)).join(" → ")}</div>` : ""}</div></div>`).join("")
      || '<div class="faint">Ancora niente: qui comparirà tutto ciò che Jarvis fa da solo.</div>';
  }

  async function load() {
    try { render(await A.api("GET", "/api/autonomy")); } catch (e) { $("au-status").textContent = e.message; }
  }

  function init() {
    $("au-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const body = { when: $("au-when").value.trim(), prompt: $("au-prompt").value.trim() };
      if (!body.when || !body.prompt) return;
      try { const r = await A.api("POST", "/api/autonomy/routines", body); A.toast(`Programmato: ${r.when_text}`); $("au-prompt").value = ""; load(); }
      catch (err) { A.toast(err.message, true); }
    });
    $("au-pilot").addEventListener("click", async () => { await A.api("POST", "/api/autonomy/autopilot"); A.toast("Autopilota avviato"); setTimeout(load, 4000); });
    $("au-list").addEventListener("click", async (e) => {
      const item = e.target.closest("[data-r]"); if (!item) return;
      const url = `/api/autonomy/routines/${encodeURIComponent(item.dataset.r)}`;
      try {
        if (e.target.closest("[data-run]")) { await A.api("POST", `${url}/run`); A.toast("Avviato: il risultato comparirà nel diario"); setTimeout(load, 5000); }
        if (e.target.closest("[data-untrust]")) { await A.api("PUT", url, { trusted: false }); A.toast("Ora chiederà di nuovo l'approvazione"); load(); }
        if (e.target.closest("[data-toggle]")) { await A.api("PUT", url, { enabled: item.classList.contains("off") }); load(); }
        if (e.target.closest("[data-del]") && confirm("Eliminare il compito?")) { await A.api("DELETE", url); load(); }
      } catch (err) { A.toast(err.message, true); }
    });
    $("au-approvals").addEventListener("click", async (e) => {
      const item = e.target.closest("[data-ap]"); if (!item) return;
      const always = !!e.target.closest("[data-always]"), yes = always || !!e.target.closest("[data-yes]");
      if (!yes && !e.target.closest("[data-no]")) return;
      try { const r = await A.api("POST", `/api/autonomy/approvals/${encodeURIComponent(item.dataset.ap)}`, { approve: yes, always }); A.toast(r.result || "Fatto"); load(); }
      catch (err) { A.toast(err.message, true); }
    });
  }

  A.tab("autonomy", {
    title: "Autonomia", init,
    load() { load(); clearInterval(timer); timer = setInterval(() => { if (A.isOn("autonomy")) load(); }, 15000); },
    leave() { clearInterval(timer); },
  });
})();
