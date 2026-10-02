(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  const ICONS = { satellite: "🎙", display: "🖥", server: "🖧", esp32: "📟", android: "📱", sensor: "🌡", other: "🔌" };
  let data = null, timer = null, codeTimer = null;

  const pct = (v) => (v == null ? "—" : `${Math.round(v)}%`);
  const ago = (t) => (!t ? "mai" : fmt.duration(Date.now() / 1000 - t) + " fa");

  function metrics(m) {
    return `<div class="nd-metrics">
      <div class="nd-metric"><b>${pct(m.cpu)}</b><span>Processore</span></div>
      <div class="nd-metric"><b>${pct(m.ram)}</b><span>Memoria</span></div>
      <div class="nd-metric"><b>${pct(m.disk)}</b><span>Disco</span></div>
      <div class="nd-metric"><b>${m.temp == null ? "—" : `${Math.round(m.temp)} °C`}</b><span>Temperatura</span></div></div>`;
  }

  function master(s) {
    const ok = !s.problems.length;
    return `<div class="nd-top"><div>
        <div class="nd-sub">Server principale</div>
        <div class="nd-title">🖧 ${fmt.esc(s.name)} <span class="badge ${ok ? "ok" : "warn"}">${ok ? "tutto operativo" : `${s.problems.length} da controllare`}</span></div>
        <div class="nd-sub mono">${fmt.esc(s.ip)} · v${fmt.esc(s.version)} (${fmt.esc(s.revision)}) · acceso da ${fmt.duration(s.uptime)}${s.update_available ? " · <span style='color:var(--amber)'>aggiornamento disponibile</span>" : ""}</div></div>
      <div class="actions">
        ${s.update_available ? '<button class="btn sm primary" data-master="update-apply">Aggiorna ora</button>' : '<button class="btn sm" data-master="update-check">Controlla aggiornamenti</button>'}
        <button class="btn sm" data-master="restart-supervisor">Riavvia Jarvis</button>
        <button class="btn sm danger" data-master="reboot">Riavvia il server</button></div></div>
      ${metrics(s.metrics)}
      <div class="nd-comps">${s.components.map((c) => `<span class="badge ${c.status === "ok" ? "ok" : c.status === "idle" ? "" : "warn"}" title="${fmt.esc(c.detail)}">${fmt.esc(c.label)}</span>`).join("")}</div>`;
  }

  function card(n) {
    const cmds = Object.entries(data.commands).map(([k, v]) => `<button class="btn sm" data-cmd="${k}" ${n.online ? "" : "disabled"}>${fmt.esc(v)}</button>`).join("");
    return `<div class="nd-card ${n.online ? "on" : ""}" data-node="${fmt.esc(n.id)}">
      <div class="nd-top"><div style="min-width:0">
        <div class="nd-title" style="font-size:16px">${ICONS[n.type] || "🔌"} ${fmt.esc(n.name)}</div>
        <div class="nd-sub">${fmt.esc(n.type_label)}${n.room ? ` · ${fmt.esc(n.room)}` : ""} · ${n.online ? '<span style="color:var(--green)">online</span>' : `offline, visto ${ago(n.last_seen)}`}</div>
        <div class="nd-sub mono">${fmt.esc(n.ip || "—")} · ${fmt.esc(n.hostname || n.id)}${n.version ? ` · ${fmt.esc(n.version)}` : ""}</div></div></div>
      ${n.metrics && Object.keys(n.metrics).length ? metrics(n.metrics) : ""}
      <div class="row"><input data-f="name" value="${fmt.esc(n.name)}" placeholder="Nome"><input data-f="room" value="${fmt.esc(n.room || "")}" placeholder="Stanza"><button class="btn sm" data-save>Salva</button></div>
      <div class="actions">${cmds}<button class="btn sm" data-settings>⚙ Impostazioni${Object.keys(n.settings || {}).length ? ` (${Object.keys(n.settings).length} personali)` : " globali"}</button><button class="btn sm danger" data-remove>Rimuovi</button></div></div>`;
  }

  function waiting() {
    const pending = (data.pending || []).map((r) => `<div class="nd-req" data-req="${fmt.esc(r.id)}">
      <div><b>${ICONS[r.type] || "🔌"} ${fmt.esc(r.name)}</b><div class="nd-sub mono">${fmt.esc(r.ip)} · ${fmt.esc(r.id)}</div></div>
      <div class="nd-fp" title="Deve coincidere con il codice mostrato dal nodo">${fmt.esc(r.fingerprint)}</div>
      <div class="actions"><button class="btn sm primary" data-approve>Approva</button><button class="btn sm danger" data-reject>Rifiuta</button></div></div>`).join("");
    const found = (data.found || []).map((f) => `<div class="nd-req"><div><b>🔎 ${fmt.esc(f.id)}</b>
      <div class="nd-sub mono">${fmt.esc(f.ip)}${f.version ? ` · agente ${fmt.esc(f.version)}` : ""}</div></div>
      <div class="nd-sub">${f.paired ? "abbinato a un altro server o revocato" : "in rete, non ancora abbinato"}</div></div>`).join("");
    return (pending ? `<div class="panel-title">Chiedono di unirsi</div>${pending}` : "")
      + (found ? `<div class="panel-title" style="margin-top:12px">Trovati in rete</div>${found}` : "");
  }

  function render() {
    $("nd-master").innerHTML = master(data.master);
    $("nd-waiting").innerHTML = waiting();
    const online = data.nodes.filter((n) => n.online).length;
    $("nd-count").textContent = data.nodes.length ? `${online} online su ${data.nodes.length}` : "";
    $("nd-grid").innerHTML = data.nodes.map(card).join("")
      || '<div class="muted-note">Nessun nodo: aggiungi un Raspberry Pi o un altro computer come satellite audio, display o server secondario.</div>';
  }

  async function load() {
    try { data = await A.api("GET", "/api/nodes"); render(); } catch (e) { $("nd-master").textContent = e.message; }
  }

  async function pairing() {
    let r;
    try { r = await A.api("POST", "/api/nodes/pairing-code"); } catch (e) { A.toast(e.message, true); return; }
    const server = `http://${data.master.ip || location.hostname}`;
    let left = r.expires_in;
    const draw = () => {
      $("nd-pairing").innerHTML = `<div>Codice di abbinamento, valido ancora ${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}:</div>
        <div class="nd-code">${fmt.esc(r.code)}</div>
        <div class="nd-sub">Sul Raspberry Pi o computer da aggiungere (Linux, Python 3) esegui:</div>
        <div class="nd-cmd">curl -sL ${fmt.esc(server)}/nodes/agent.py -o jarvis-node.py
sudo python3 jarvis-node.py --server ${fmt.esc(server)} --code ${fmt.esc(r.code)} --name "Cucina" --type satellite --install</div>
        <div class="nd-sub">Cambia nome e tipo a piacere (satellite, display, server, sensor). Con --install l'agente parte da solo a ogni accensione.</div>
        <div class="nd-sub" style="margin-top:10px">Oppure, senza codice: il nodo trova Jarvis da solo nella rete e tu lo approvi qui confrontando il codice che mostra.</div>
        <div class="nd-cmd">curl -sL ${fmt.esc(server)}/nodes/agent.py -o jarvis-node.py
sudo python3 jarvis-node.py --join --name "Cucina" --type satellite --install</div>
        <div class="nd-sub">Se il server cambia indirizzo (DHCP), i nodi lo ritrovano da soli e si aggiornano automaticamente.</div>`;
    };
    clearInterval(codeTimer); draw();
    codeTimer = setInterval(() => { left -= 1; if (left <= 0) { clearInterval(codeTimer); $("nd-pairing").innerHTML = ""; load(); } else draw(); }, 1000);
  }

  async function masterAction(action) {
    const ask = { reboot: "Riavviare il server? Jarvis sarà offline per qualche minuto.", "restart-supervisor": "Riavviare Jarvis?" }[action];
    if (ask && !confirm(ask)) return;
    try { await A.api("POST", `/api/actions/${action}`); A.toast("Comando inviato"); setTimeout(load, 1500); } catch (e) { A.toast(e.message, true); }
  }

  async function decide(el, approve) {
    const id = encodeURIComponent(el.dataset.req);
    try {
      if (approve) await A.api("POST", `/api/nodes/requests/${id}/approve`);
      else await A.api("DELETE", `/api/nodes/requests/${id}`);
      A.toast(approve ? "Nodo approvato: si collega entro pochi secondi" : "Richiesta rifiutata"); load();
    } catch (err) { A.toast(err.message, true); }
  }

  function init() {
    $("nd-pair").addEventListener("click", pairing);
    $("nd-waiting").addEventListener("click", (e) => {
      const el = e.target.closest("[data-req]"); if (!el) return;
      if (e.target.closest("[data-approve]")) decide(el, true);
      else if (e.target.closest("[data-reject]")) decide(el, false);
    });
    $("nd-master").addEventListener("click", (e) => { const b = e.target.closest("[data-master]"); if (b) masterAction(b.dataset.master); });
    $("nd-grid").addEventListener("click", async (e) => {
      const el = e.target.closest("[data-node]"); if (!el) return;
      const id = el.dataset.node, url = `/api/nodes/${encodeURIComponent(id)}`;
      try {
        if (e.target.closest("[data-save]")) {
          await A.api("PUT", url, { name: el.querySelector('[data-f="name"]').value, room: el.querySelector('[data-f="room"]').value });
          A.toast("Salvato"); return load();
        }
        if (e.target.closest("[data-settings]")) return A.nodeSettings.open(id);
        const cmd = e.target.closest("[data-cmd]");
        if (cmd) { await A.api("POST", `${url}/command/${cmd.dataset.cmd}`); A.toast("Comando in coda: il nodo lo riceve entro 30 secondi"); return; }
        if (e.target.closest("[data-remove]") && confirm("Rimuovere il nodo? Il suo accesso viene revocato subito.")) { await A.api("DELETE", url); load(); }
      } catch (err) { A.toast(err.message, true); }
    });
  }

  A.tab("nodes", {
    title: "Nodi e server", init,
    load() { load(); clearInterval(timer); timer = setInterval(() => { if (A.isOn("nodes")) load(); }, 10000); },
    leave() { clearInterval(timer); clearInterval(codeTimer); },
  });
})();
