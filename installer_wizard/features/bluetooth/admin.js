(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  const ICONS = { Auricolari: "🎧", Cuffie: "🎧", Cassa: "🔊", Microfono: "🎙", Telefono: "📱", Computer: "💻", Tastiera: "⌨", Mouse: "🖱", Controller: "🎮" };
  let data = null, timer = null;

  function status(c) {
    if (!data.enabled) return "<b>Bluetooth disattivato</b>Riattivalo dalle Funzionalità.";
    if (!c.present) return `<b>Nessun adattatore Bluetooth</b><span class="bt-empty">Questo server non ha il Bluetooth. Collega una chiavetta USB Bluetooth 5.x compatibile con Linux (ad esempio con chip Realtek RTL8761B o Intel): Jarvis la riconosce da solo, installa ciò che serve e la rende pronta in un minuto.</span>`;
    if (!c.installed) return "<b>Adattatore rilevato</b>Sto installando il supporto Bluetooth, attendi qualche istante…";
    return `<b>${c.powered ? "🟢" : "⚪"} ${fmt.esc(c.name || "Bluetooth")}</b><span class="faint mono">${fmt.esc(c.address || "")}</span>${data.scanning ? " · <span style='color:var(--cyan)'>ricerca in corso…</span>" : ""}`;
  }

  const byMac = () => Object.fromEntries(data.devices.map((d) => [d.mac, d]));

  function orderList(kind) {
    const devs = byMac(), order = data.prefs[`${kind}_order`], active = data.routing[kind === "output" ? "output" : "input"];
    return order.filter((m) => devs[m]).map((m, i) => {
      const d = devs[m];
      const sub = [m === active ? '<b style="color:var(--cyan)">▶ in uso</b>' : "", d.connected ? '<span style="color:var(--green)">collegato</span>' : "non collegato",
        d.battery != null ? `🔋 ${d.battery}%` : "", fmt.esc(d.kind)].filter(Boolean).join(" · ");
      return A.prioItem(m, i, d.name, sub, !d.connected, false);
    }).join("") || '<div class="muted-note" style="margin:6px">Nessun dispositivo: abbinane uno qui sotto.</div>';
  }

  function select(d, name, options) {
    return `<label>${name === "role" ? "Uso" : "Profilo audio"}<select data-set="${name}">${Object.entries(options).map(([k, v]) =>
      `<option value="${k}" ${d.settings[name] === k ? "selected" : ""}>${fmt.esc(v)}</option>`).join("")}</select></label>`;
  }

  function card(d) {
    const btns = [!d.paired ? '<button class="btn sm primary" data-bt="pair">Abbina</button>' : "",
      d.paired && !d.connected ? '<button class="btn sm primary" data-bt="connect">Collega</button>' : "",
      d.connected ? '<button class="btn sm" data-bt="disconnect">Scollega</button>' : "",
      d.paired ? '<button class="btn sm danger" data-bt="forget">Dimentica</button>' : ""].join("");
    const audio = d.audio_out || d.audio_in;
    return `<div class="bt-card ${d.connected ? "on" : ""}" data-mac="${fmt.esc(d.mac)}">
      <div class="bt-top"><div class="bt-ico">${ICONS[d.kind] || "ᛒ"}</div><div style="min-width:0">
        <div class="bt-name">${fmt.esc(d.name)}</div>
        <div class="bt-meta">${fmt.esc(d.kind)} · ${fmt.esc(d.mac)}${d.battery != null ? ` · 🔋 ${d.battery}%` : ""}</div>
        <div class="bt-meta">${d.connected ? '<span class="badge ok">collegato</span>' : d.paired ? '<span class="badge">abbinato</span>' : '<span class="badge warn">nuovo</span>'}
          ${d.audio_out ? '<span class="badge">🔊</span>' : ""}${d.audio_in ? '<span class="badge">🎙</span>' : ""}</div></div></div>
      ${d.paired && audio ? `${select(d, "role", data.roles)}${d.audio_in ? select(d, "profile", data.profiles) : ""}
        <label class="switch" style="flex-direction:row"><input type="checkbox" data-set="autoconnect" ${d.settings.autoconnect ? "checked" : ""}> Riconnetti da solo</label>` : ""}
      <div class="actions">${btns}</div></div>`;
  }

  function render() {
    const c = data.controller;
    $("bt-status").innerHTML = status(c);
    $("bt-scan").disabled = !c.installed || data.scanning;
    $("bt-scan").textContent = data.scanning ? "Ricerca…" : "Cerca dispositivi";
    document.querySelectorAll("[data-bt-flag]").forEach((x) => { x.checked = !!data.prefs[x.dataset.btFlag]; });
    $("bt-out").innerHTML = orderList("output");
    $("bt-in").innerHTML = orderList("input");
    const devs = [...data.devices].sort((a, b) => (b.connected - a.connected) || (b.paired - a.paired) || a.name.localeCompare(b.name, "it"));
    $("bt-devices").innerHTML = devs.map(card).join("") || `<div class="bt-empty">${c.installed ? "Nessun dispositivo. Metti le cuffie o la cassa in modalità abbinamento e premi «Cerca dispositivi»." : "In attesa dell'adattatore."}</div>`;
  }

  async function load() {
    try { data = await A.api("GET", "/api/bluetooth"); render(); } catch (e) { $("bt-status").textContent = e.message; }
  }

  async function save(body) {
    try { data = await A.api("PUT", "/api/bluetooth/prefs", body); render(); } catch (e) { A.toast(e.message, true); load(); }
  }

  async function act(mac, action) {
    if (action === "forget" && !confirm("Dimenticare questo dispositivo? Dovrai abbinarlo di nuovo.")) return;
    A.toast(action === "pair" ? "Abbinamento in corso: tieni il dispositivo in modalità abbinamento" : "Attendi…");
    try { data = await A.api("POST", `/api/bluetooth/devices/${encodeURIComponent(mac)}/${action}`); render(); A.toast("Fatto"); } catch (e) { A.toast(e.message, true); load(); }
  }

  function init() {
    A.makeSortable($("bt-out"), (items) => save({ output_order: items }));
    A.makeSortable($("bt-in"), (items) => save({ input_order: items }));
    document.querySelectorAll("[data-bt-flag]").forEach((x) => x.addEventListener("change", () => save({ [x.dataset.btFlag]: x.checked })));
    $("bt-scan").addEventListener("click", async () => {
      try { await A.api("POST", "/api/bluetooth/scan"); data.scanning = true; render(); setTimeout(load, 21000); } catch (e) { A.toast(e.message, true); }
    });
    $("bt-devices").addEventListener("click", (e) => { const b = e.target.closest("[data-bt]"); if (b) act(b.closest("[data-mac]").dataset.mac, b.dataset.bt); });
    $("bt-devices").addEventListener("change", (e) => {
      const el = e.target.closest("[data-set]"); if (!el) return;
      const mac = el.closest("[data-mac]").dataset.mac;
      save({ devices: { [mac]: { [el.dataset.set]: el.type === "checkbox" ? el.checked : el.value } } });
    });
  }

  A.tab("bluetooth", {
    title: "Bluetooth", init,
    load() { load(); clearInterval(timer); timer = setInterval(() => { if (A.isOn("bluetooth")) load(); }, 5000); },
    leave() { clearInterval(timer); },
  });
})();
