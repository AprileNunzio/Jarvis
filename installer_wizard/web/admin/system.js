(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  const PHASE_DOT = { READY: "ok", DEGRADED: "warn", ERROR: "down", INSTALLING: "warn", BOOTING: "warn", UPDATING: "warn" };
  const STEP_STATUS = { pending: "in attesa", checking: "verifica", running: "in corso", retrying: "nuovo tentativo", done: "operativo", failed: "errore", skipped: "saltato", background: "in background dopo l'avvio" };
  const RESTARTABLE = { core: 1, qdrant: 1, ollama: 1, docker: 1, kiosk: 1 };

  function renderPhase(s) {
    $("phase-dot").className = `dot ${PHASE_DOT[s.phase] || "idle"}`;
    $("phase-lbl").textContent = s.phase_label;
    $("progress-lbl").textContent = s.phase === "READY" ? `v${s.supervisor_version}` : `${Math.floor(s.progress)}%`;
    $("cur-msg").textContent = s.message;
    $("cur-detail").textContent = s.detail || "";
    $("cur-err").textContent = s.last_error || "";
    $("b-progress").style.width = `${s.progress}%`;
    const b = s.brains || {};
    $("boot-info").textContent = `Avvio n. ${s.boot_count} · fase attiva da ${fmt.duration(Date.now() / 1000 - s.phase_since)} · conversazione ${b.chat || "—"} · ragionamento ${b.deep || s.llm_model || "—"}${b.last ? ` · ultima risposta: ${b.last}` : ""}`;
  }

  function renderSystem(sys) {
    if (!sys.mem_total) return;
    $("s-cpu").textContent = `${sys.cpu_percent.toFixed(0)}%`; $("b-cpu").style.width = `${sys.cpu_percent}%`;
    $("s-load").textContent = `${sys.cpu_count} core · carico ${sys.load.join(" / ")}${sys.temperature ? ` · ${sys.temperature} °C` : ""}`;
    $("s-mem").textContent = `${sys.mem_percent.toFixed(0)}%`; $("b-mem").style.width = `${sys.mem_percent}%`;
    $("s-mem2").textContent = `${fmt.bytes(sys.mem_used)} di ${fmt.bytes(sys.mem_total)}`;
    $("s-disk").textContent = `${sys.disk_percent.toFixed(0)}%`; $("b-disk").style.width = `${sys.disk_percent}%`;
    $("s-disk2").textContent = `${fmt.bytes(sys.disk_used)} di ${fmt.bytes(sys.disk_total)}`;
    $("s-up").textContent = fmt.duration(sys.uptime);
    $("s-host").textContent = `${sys.hostname} · ${sys.ip} · ↓${fmt.rate(sys.net_rx_rate)} ↑${fmt.rate(sys.net_tx_rate)}`;
  }

  function renderComponents(s) {
    $("comp-body").innerHTML = Object.entries(s.components || {}).map(([k, c]) => `
      <tr><td><span class="dot ${c.status}"></span></td><td>${fmt.esc(c.label)}<div class="faint mono">${fmt.esc(c.detail)}</div></td>
      <td><span class="badge ${c.status}">${c.status === "ok" ? "operativo" : c.status === "warn" ? "attenzione" : "guasto"}</span></td>
      <td style="text-align:right">${RESTARTABLE[k] ? `<button class="btn sm" data-action="restart-component" data-body='{"component":"${k}"}' data-confirm="Riavviare ${fmt.esc(c.label)}?">Riavvia</button>` : ""}</td></tr>`).join("")
      || `<tr><td colspan="4" class="faint">Diagnosi disponibile quando il sistema è operativo.</td></tr>`;
  }

  function renderSteps(s) {
    $("steps-body").innerHTML = s.catalog.map((c) => {
      const r = s.steps[c.id] || { status: "pending" };
      const prog = r.status === "running" ? ` ${r.progress}%` : "";
      return `<tr><td>${fmt.esc(c.title)}<div class="faint" style="font-size:12px">${fmt.esc(c.description)}${c.critical ? "" : " · opzionale"}</div></td>
        <td><span class="badge ${r.status}">${STEP_STATUS[r.status] || r.status}${prog}</span></td>
        <td class="mono">${r.attempts || 0}</td><td class="mono">${r.duration ? fmt.duration(r.duration) : "—"}</td>
        <td style="max-width:320px; font-size:12px" class="${r.error ? "" : "dim"}">${fmt.esc(r.error || r.message || "")}</td>
        <td style="text-align:right"><button class="btn sm" data-action="rerun-step" data-body='{"step":"${c.id}"}' data-confirm="Rieseguire lo step '${fmt.esc(c.title)}'?" ${s.busy ? "disabled" : ""}>Riesegui</button></td></tr>`;
    }).join("");
  }

  function renderEvents(s) {
    $("events-body").innerHTML = (s.events || []).slice().reverse().map((e) => `
      <tr><td class="mono">${new Date(e.ts).toLocaleString("it-IT")}</td><td><span class="badge ${e.level === "ERROR" ? "down" : e.level === "WARN" ? "warn" : "ok"}">${e.level}</span></td>
      <td class="mono">${fmt.esc(e.component)}</td><td>${fmt.esc(e.msg)}</td></tr>`).join("");
  }

  function renderUpdate(u) {
    $("upd-body").innerHTML = `
      <tr><td class="dim">Versione locale</td><td class="mono">${fmt.esc((u.local_rev || "—").slice(0, 10))}</td></tr>
      <tr><td class="dim">Versione remota</td><td class="mono">${fmt.esc((u.remote_rev || "—").slice(0, 10))}</td></tr>
      <tr><td class="dim">Con test superati</td><td class="mono">${fmt.esc((u.target_rev || "—").slice(0, 10))}</td></tr>
      <tr><td class="dim">Stato</td><td>${u.available ? '<span class="badge warn">aggiornamento disponibile</span>' : u.remote_rev && u.remote_rev !== u.local_rev ? `<span class="badge">${fmt.esc(u.ci_note || "in attesa dei test")}</span>` : '<span class="badge ok">aggiornato</span>'}</td></tr>
      <tr><td class="dim">Ultimo controllo</td><td class="mono">${u.last_check ? new Date(u.last_check).toLocaleString("it-IT") : "—"}</td></tr>
      <tr><td class="dim">Ultimo esito</td><td>${fmt.esc(u.last_result || "—")}</td></tr>`;
    $("upd-log").textContent = (u.changelog && u.changelog.length) ? u.changelog.join("\n") : "Nessuna novità in attesa.";
  }

  async function loadConfig() {
    const d = await A.api("GET", "/api/config");
    $("config-fields").innerHTML = d.editable.map((f) => `<div><label for="cfg-${f.key}">${fmt.esc(f.label)}</label>
      <input id="cfg-${f.key}" name="${f.key}" value="${fmt.esc(f.value)}" ${f.secret ? 'type="password" placeholder="non impostata"' : ""} autocomplete="off"></div>`).join("");
    $("config-system").innerHTML = Object.entries(d.system).map(([k, v]) => `<tr><td class="mono dim">${fmt.esc(k)}</td><td class="mono">${fmt.esc(v || "—")}</td></tr>`).join("");
  }

  async function loadLogs() {
    try {
      const d = await A.api("GET", `/api/logs/${$("log-src").value}?lines=400`);
      const el = $("log-text"); const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 30;
      el.textContent = d.text || "(vuoto)"; if (atBottom) el.scrollTop = el.scrollHeight;
    } catch (e) { $("log-text").textContent = e.message; }
  }

  function init() {
    document.addEventListener("click", async (e) => {
      const b = e.target.closest("[data-action]");
      if (!b) return;
      if (b.dataset.confirm && !confirm(b.dataset.confirm)) return;
      const body = b.dataset.body ? JSON.parse(b.dataset.body) : undefined;
      b.disabled = true;
      try {
        const r = await A.api("POST", `/api/actions/${b.dataset.action}`, body);
        if (b.dataset.action === "update-check") { renderUpdate(r); A.toast(r.available ? "Aggiornamento disponibile" : "Jarvis è aggiornato"); }
        else A.toast(r.message || (r.ok === false ? "Operazione non riuscita" : "Operazione avviata"), r.ok === false);
      } catch (err) { A.toast(err.message, true); }
      finally { setTimeout(() => (b.disabled = false), 1500); }
    });
    $("config-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const body = {}; new FormData(e.target).forEach((v, k) => (body[k] = v));
      try { const r = await A.api("PUT", "/api/config", body); A.toast(r.changed.length ? `Salvato: ${r.changed.join(", ")}${r.applying.length ? " — applicazione in corso" : ""}` : "Nessuna modifica"); loadConfig(); }
      catch (err) { A.toast(err.message, true); }
    });
    $("log-src").addEventListener("change", loadLogs);
    $("log-refresh").addEventListener("click", loadLogs);
    setInterval(() => { if (A.isOn("logs") && $("log-auto").checked) loadLogs(); }, 4000);
  }

  A.tab("overview", { init, onState(s) { renderPhase(s); renderSystem(s.system || {}); renderComponents(s); renderSteps(s); renderEvents(s); if (s.update) renderUpdate(s.update); } });
  A.tab("config", { load: loadConfig });
  A.tab("logs", { load: loadLogs });
  A.tab("updates", { load: () => A.api("POST", "/api/actions/update-check").then(renderUpdate).catch((e) => A.toast(e.message, true)) });
})();
