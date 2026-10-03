(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  const FLAVOR = { ollama: "Ollama", openai: "Compatibile OpenAI" };
  let data = null;

  const ref = (pid, model) => `cloud:${pid}/${model}`;

  function form() {
    return { name: $("sv-name").value.trim(), flavor: $("sv-flavor").value, url: $("sv-url").value.trim(), key: $("sv-key").value.trim() };
  }

  function card(s) {
    const badge = s.online ? '<span class="badge ok">raggiungibile</span>' : '<span class="badge warn">non risponde</span>';
    const rows = s.models.map((m) => `<div class="sv-model"><span class="mono">${fmt.esc(m)}</span><span class="actions">
        ${A.brainRoles.addButtons(ref(s.id, m), `data-m="${fmt.esc(m)}"`)}</span></div>`).join("")
      || `<div class="faint">${s.online ? "Nessun modello installato su questo server." : fmt.esc(s.error)}</div>`;
    return `<div class="panel cl-card" data-sid="${fmt.esc(s.id)}">
      <div class="cl-head"><span class="cl-name">🖧 ${fmt.esc(s.name)}</span><span>${badge}</span></div>
      <div class="cl-notes">${fmt.esc(FLAVOR[s.flavor] || s.flavor)} · <span class="mono">${fmt.esc(s.url)}</span>${s.has_key ? " · 🔑" : ""}</div>
      <div class="sv-models">${rows}</div>
      <div class="actions"><button class="btn sm" data-act="refresh">↻ Aggiorna</button><button class="btn sm danger" data-act="remove">Rimuovi</button></div>
    </div>`;
  }

  function render() {
    $("sv-list").innerHTML = data.servers.map(card).join("") || '<div class="faint">Nessun server aggiunto.</div>';
  }

  async function load() {
    try {
      data = await A.api("GET", "/api/brains/servers"); render();
      const n = data.servers.reduce((t, s) => t + s.models.length, 0);
      $("sv-stamp").textContent = `${data.servers.length} server · ${n} modelli · aggiornato alle ${new Date().toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`;
    }
    catch (e) { $("sv-list").innerHTML = `<div class="faint">${fmt.esc(e.message)}</div>`; }
  }

  async function test() {
    $("sv-res").textContent = "Prova in corso…";
    try {
      const r = await A.api("POST", "/api/brains/servers/test", form());
      $("sv-res").innerHTML = r.ok ? `✅ ${fmt.esc(r.root)} risponde: ${r.models.length} modelli${r.models.length ? ` (${r.models.slice(0, 6).map(fmt.esc).join(", ")}${r.models.length > 6 ? "…" : ""})` : ""}`
        : `⚠ ${fmt.esc(r.error)}`;
      return r.ok;
    } catch (e) { $("sv-res").textContent = `⚠ ${e.message}`; return false; }
  }

  async function add(e) {
    e.preventDefault();
    const body = form();
    if (!body.url) return A.toast("Scrivi l'indirizzo del server", true);
    if (!(await test())) {
      if (!confirm("Il server non risponde: aggiungerlo comunque?")) return;
      body.force = true;
    }
    try {
      await A.api("POST", "/api/brains/servers", body);
      ["sv-name", "sv-url", "sv-key"].forEach((id) => { $(id).value = ""; });
      A.toast(`Server aggiunto: scegli i modelli con ${A.brainRoles.addHint()}`);
      load();
    } catch (err) { A.toast(err.message, true); }
  }

  async function act(e) {
    const el = e.target.closest("[data-sid]"); if (!el) return;
    const sid = el.dataset.sid, add = e.target.closest("[data-add]"), b = e.target.closest("[data-act]");
    if (add) { await A.brain.addTo(add.dataset.add, ref(sid, add.dataset.m), true); return load(); }
    if (!b) return;
    if (b.dataset.act === "refresh") return load();
    if (b.dataset.act === "remove") {
      const s = data.servers.find((x) => x.id === sid);
      if (!confirm(`Rimuovere ${s ? s.name : sid}? I suoi modelli escono anche dalle liste ⚡ e 🧠.`)) return;
      try { await A.api("DELETE", `/api/brains/servers/${encodeURIComponent(sid)}`); A.toast("Server rimosso"); load(); A.brain.reload(); }
      catch (err) { A.toast(err.message, true); }
    }
  }

  function init() {
    setInterval(() => { if (A.isOn("models") && $("br-view-servers").classList.contains("on") && !document.hidden) load(); }, 30000);
    $("br-source").addEventListener("click", (e) => { if (e.target.closest('[data-v="servers"]')) load(); });
    $("sv-test").addEventListener("click", test);
    $("sv-form").addEventListener("submit", add);
    $("sv-list").addEventListener("click", act);
    $("sv-flavor").addEventListener("change", () => {
      $("sv-url").placeholder = $("sv-flavor").value === "ollama" ? "es. 192.168.1.50:11434" : "es. http://192.168.1.50:1234/v1";
    });
  }

  A.brainServers = { init, load };
})();
