(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  const HM_STATUS = { online: ["collegato", "ok"], connecting: ["collegamento…", "warn"], offline: ["non raggiungibile", "down"],
    auth_failed: ["token rifiutato", "down"], not_configured: ["da configurare", "warn"], disabled: ["disattivato", ""], starting: ["avvio…", "warn"] };
  const KIND = { motion: "🏃", presence: "🧍", opening: "🚪", person: "👤", device_tracker: "📍", lock: "🔒", alarm_control_panel: "🚨", light: "💡", cover: "🪟", climate: "🌡", media_player: "📺" };
  const hmTime = (ts) => ts ? new Date(ts * 1000).toLocaleString("it-IT", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" }) : "—";
  let hmDev = { devices: [], loose: [] }, hmSel = null;

  function renderSummary(h) {
    const st = HM_STATUS[h.status] || [h.status, ""];
    $("hm-status").innerHTML = `<span class="badge ${st[1]}">${fmt.esc(st[0])}</span>`;
    $("hm-status2").textContent = h.status === "online" ? `${h.ha_name || ""} · HA ${h.ha_version} · studiata ${hmTime(h.synced_at)} in ${h.sync_ms} ms` : (h.error || h.url || "");
    $("hm-areas").textContent = h.counts.areas;
    $("hm-areas2").textContent = `${h.counts.floors} piani · sensori di presenza in ${h.counts.motion_rooms} stanze`;
    $("hm-devices").textContent = h.counts.devices;
    $("hm-devices2").textContent = `${h.counts.entities} entità, ${h.counts.controllable} comandabili`;
    $("hm-cmds").textContent = h.stats.commands;
    $("hm-cmds2").textContent = `media ${h.stats.avg_ms} ms · ${h.stats.llm} tradotti dal cervello · ${h.counts.learned} frasi imparate`;
    $("hm-protos").innerHTML = h.protocols.map((p) => `<span class="proto ${fmt.esc(p.key)}" style="font-size:12px; padding:4px 12px">${fmt.esc(p.label)} · ${fmt.esc(p.value)}</span>`).join("") || '<span class="faint">Nessun dispositivo ancora</span>';
    $("hm-summary").textContent = h.summary ? `Ho studiato la casa: ${h.summary}.` : "";
  }

  function renderRooms(h) {
    $("hm-rooms").innerHTML = h.rooms.map((r) => `<div class="room ${r.occupied ? "occ" : ""}">
        <div class="nm"><span class="dot ${r.occupied ? "ok" : r.has_sensors ? "idle" : ""}"></span>${fmt.esc(r.name)}</div>
        <div class="fl">${fmt.esc(r.floor || "")}${r.devices ? ` · ${r.devices} dispositivi` : ""}</div>
        <div class="lb">${fmt.esc(r.label)}</div>
        <div class="mt">${r.temperature != null ? `<span>🌡 ${r.temperature} °C</span>` : ""}${r.humidity != null ? `<span>💧 ${Math.round(r.humidity)}%</span>` : ""}
          ${r.lights_on ? `<span>💡 ${r.lights_on} accese</span>` : ""}${r.open.length ? `<span style="color:var(--amber)">🚪 ${fmt.esc(r.open.join(", "))}</span>` : ""}</div>
        <input data-alias="area:${fmt.esc(r.area_id)}" value="${fmt.esc(r.aliases.join(", "))}" placeholder="Altri nomi${r.ha_aliases.length ? " (HA: " + fmt.esc(r.ha_aliases.join(", ")) + ")" : ""}"></div>`).join("")
      || '<div class="faint">Nessuna stanza: assegna le aree ai dispositivi in Home Assistant.</div>';
  }

  function renderFilters(h) {
    const pSel = $("hm-proto"), aSel = $("hm-area"), pv = pSel.value, av = aSel.value;
    pSel.innerHTML = '<option value="">Tutti i protocolli</option>' + h.protocols.filter((p) => p.key !== "matter_all").map((p) => `<option value="${fmt.esc(p.key)}">${fmt.esc(p.label)}</option>`).join("") + (h.protocols.some((p) => p.key === "matter_all") ? '<option value="matter_all">Matter (tutti)</option>' : "");
    aSel.innerHTML = '<option value="">Tutte le stanze</option>' + hmDev.areas.map((a) => `<option value="${fmt.esc(a.area_id)}">${fmt.esc(a.name)}</option>`).join("") + '<option value="-">Senza stanza</option>';
    pSel.value = pv; aSel.value = av;
  }

  async function loadHome() {
    let h;
    try { [h, hmDev] = await Promise.all([A.api("GET", "/api/home"), A.api("GET", "/api/home/devices")]); } catch (e) { A.toast(e.message, true); return; }
    renderSummary(h);
    renderHomeConnect(h);
    renderRooms(h);
    renderFilters(h);
    renderHomeDevices();
    if (hmSel) showHomeDevice(hmSel);
    loadHomeActivity();
  }

  function renderHomeConnect(h) {
    const box = $("hm-connect");
    if ((h.configured && h.status !== "auth_failed") || h.status === "online") { box.style.display = "none"; return; }
    box.style.display = "block";
    box.innerHTML = `<div class="panel-title">Collega Home Assistant</div>
      <div class="muted-note" style="margin-bottom:12px">In Home Assistant apri il tuo profilo → <b>Sicurezza</b> → <b>Token di accesso a lunga durata</b> → Crea token. Incollalo qui: Jarvis si collega da solo e studia tutta la casa.</div>
      ${h.discovered.length ? `<div class="muted-note" style="margin-bottom:10px">Trovato in rete: ${h.discovered.map((u) => `<button class="btn sm" data-hmurl="${fmt.esc(u)}">${fmt.esc(u)}</button>`).join(" ")}</div>` : ""}
      <div class="form-grid"><div><label>Indirizzo</label><input id="hm-url" value="${fmt.esc(h.url || "")}" placeholder="http://homeassistant.local:8123"></div>
        <div><label>Token</label><input id="hm-token" type="password" placeholder="${h.configured ? "token salvato: incollane uno nuovo" : "incolla il token"}" autocomplete="off"></div></div>
      <div class="actions" style="margin-top:12px"><button class="btn primary" id="hm-save">Collega</button></div>`;
  }

  function renderHomeDevices() {
    const q = ($("hm-filter").value || "").toLowerCase(), p = $("hm-proto").value, a = $("hm-area").value;
    const list = hmDev.devices.filter((d) => !d.disabled && (!p || d.protocol === p || (p === "matter_all" && d.matter))
      && (!a || (a === "-" ? !d.area_id : d.area_id === a))
      && (!q || JSON.stringify([d.name, d.area, d.manufacturer, d.model, d.integration, d.protocol_label, d.entities.map((e) => e.name)]).toLowerCase().includes(q)));
    $("hm-body").innerHTML = list.map((d) => `<tr data-dev="${fmt.esc(d.device_id)}" style="cursor:pointer">
        <td>${fmt.esc(d.name)}${d.via ? `<div class="faint" style="font-size:11px">tramite ${fmt.esc(d.via)}</div>` : ""}</td>
        <td style="font-size:12px">${fmt.esc(d.area || "—")}</td>
        <td style="font-size:12px">${fmt.esc(d.manufacturer || "—")}<div class="faint">${fmt.esc(d.model || "")}${d.sw_version ? " · fw " + fmt.esc(d.sw_version) : ""}</div></td>
        <td><span class="proto ${fmt.esc(d.protocol)}">${fmt.esc(d.protocol_label)}</span>${d.matter && d.protocol !== "matter" ? ' <span class="proto matter">Matter</span>' : ""}</td>
        <td class="mono">${fmt.esc(d.integration || "")}</td>
        <td class="mono">${d.entities.length}</td></tr>`).join("")
      || '<tr><td colspan="6" class="faint">Nessun dispositivo corrisponde ai filtri.</td></tr>';
  }

  function showHomeDevice(id) {
    const d = hmDev.devices.find((x) => x.device_id === id); if (!d) return;
    hmSel = id;
    const panel = $("hm-detail"); panel.style.display = "block";
    panel.innerHTML = `<div class="panel-title">${fmt.esc(d.name)} <span class="proto ${fmt.esc(d.protocol)}">${fmt.esc(d.protocol_label)}</span></div>
      <table style="margin-bottom:14px"><tbody>
        <tr><td class="dim">Produttore e modello</td><td>${fmt.esc([d.manufacturer, d.model, d.model_id].filter(Boolean).join(" · ") || "—")}</td></tr>
        <tr><td class="dim">Firmware / hardware</td><td>${fmt.esc([d.sw_version, d.hw_version].filter(Boolean).join(" / ") || "—")}</td></tr>
        <tr><td class="dim">Integrazione</td><td class="mono">${fmt.esc(d.integration || "—")}${d.via ? ` · collegato tramite ${fmt.esc(d.via)}` : ""}</td></tr>
        <tr><td class="dim">Stanza</td><td>${fmt.esc(d.area || "nessuna (assegnala in Home Assistant)")}</td></tr></tbody></table>
      <div class="panel-title">Entità e come comandarle</div>
      ${d.entities.map((e) => `<div class="ent"><div>${fmt.esc(e.name)} <span class="faint mono">${fmt.esc(e.entity_id)}</span></div><div class="dim">${fmt.esc(e.state)}</div>
        ${e.controllable ? `<div class="cp">Comandabile${e.capabilities.length ? ": " + fmt.esc(e.capabilities.join(", ")) : ""}</div>
        <input data-alias="entity:${fmt.esc(e.entity_id)}" value="${fmt.esc(e.jarvis_aliases.join(", "))}" placeholder="Altri nomi con cui la chiami (separati da virgola)">` : e.category ? `<div class="cp">${e.category === "diagnostic" ? "Diagnostica" : "Configurazione"}</div>` : ""}</div>`).join("") || '<div class="faint">Nessuna entità attiva.</div>'}`;
  }

  async function loadHomeActivity() {
    let a; try { a = await A.api("GET", "/api/home/activity?hours=24"); } catch (e) { return; }
    $("hm-activity").innerHTML = a.activity.map((x) => `<div><span class="mono faint">${hmTime(x.ts)}</span> ${KIND[x.kind] || "•"} ${fmt.esc(x.name)} → ${fmt.esc(x.state)}${x.area ? ` <span class="faint">· ${fmt.esc(x.area)}</span>` : ""}</div>`).join("") || '<div class="faint">Nessuna attività registrata.</div>';
    $("hm-commands").innerHTML = a.commands.map((c) => `<div><span class="mono faint">${hmTime(c.ts)}</span> ${c.ok ? "✓" : '<span style="color:var(--red)">✕</span>'} ${fmt.esc(c.text || "—")} <span class="faint">· ${fmt.esc(c.source)} · ${c.ms} ms</span></div>`).join("") || '<div class="faint">Nessun comando ancora.</div>';
  }

  async function homeTest(run) {
    const text = $("hm-q").value.trim(); if (!text) return;
    try { const r = await A.api("POST", "/api/home/test", { text, run });
      $("hm-out").innerHTML = `<div style="margin-top:10px">${r.speech ? fmt.esc(r.speech) : '<span class="faint">Non riguarda la casa (o non l\'ho capita): la girerei al cervello.</span>'} <span class="faint">· analisi in ${r.parse_ms} ms${r.agent ? " · " + fmt.esc(r.agent) : ""}</span></div>
        ${r.plan ? `<div class="hm-plan mono">${fmt.esc(JSON.stringify(r.plan, null, 2))}</div>` : ""}`;
      if (run) setTimeout(loadHome, 800);
    } catch (e) { A.toast(e.message, true); }
  }

  function init() {
    $("hm-try").addEventListener("click", () => homeTest(false));
    $("hm-run").addEventListener("click", () => homeTest(true));
    $("hm-q").addEventListener("keydown", (e) => { if (e.key === "Enter") homeTest(false); });
    $("hm-filter").addEventListener("input", renderHomeDevices);
    $("hm-proto").addEventListener("change", renderHomeDevices);
    $("hm-area").addEventListener("change", renderHomeDevices);
    $("hm-body").addEventListener("click", (e) => { const r = e.target.closest("tr[data-dev]"); if (r) showHomeDevice(r.dataset.dev); });
    $("hm-sync").addEventListener("click", async (e) => {
      e.target.disabled = true;
      try { await A.api("POST", "/api/home/sync"); A.toast("Casa ristudiata"); loadHome(); } catch (err) { A.toast(err.message, true); }
      finally { e.target.disabled = false; }
    });
    $("hm-forget").addEventListener("click", async () => {
      if (!confirm("Dimenticare le frasi che Jarvis ha imparato per la casa?")) return;
      try { await A.api("DELETE", "/api/home/learned"); A.toast("Frasi dimenticate"); loadHome(); } catch (e) { A.toast(e.message, true); }
    });
    $("tab-home").addEventListener("change", async (e) => {
      const t = e.target.dataset.alias; if (!t) return;
      try { await A.api("PUT", "/api/home/aliases", { target: t, names: e.target.value }); A.toast("Nomi salvati: Jarvis li usa subito"); } catch (err) { A.toast(err.message, true); }
    });
    $("hm-connect").addEventListener("click", async (e) => {
      const u = e.target.dataset.hmurl; if (u) { $("hm-url").value = u; return; }
      if (e.target.id !== "hm-save") return;
      const body = { HOME_ASSISTANT_URL: $("hm-url").value.trim() };
      if ($("hm-token").value.trim()) body.HOME_ASSISTANT_TOKEN = $("hm-token").value.trim();
      try { await A.api("PUT", "/api/features/home_assistant/settings", body); A.toast("Salvato: collegamento in corso"); setTimeout(loadHome, 4000); setTimeout(loadHome, 12000); }
      catch (err) { A.toast(err.message, true); }
    });
  }

  function onState(s) {
    const rev = s.home ? `${s.home.status}:${s.home.rev}` : "";
    if (rev === window.__homeRev) return;
    window.__homeRev = rev;
    if (A.isOn("home") && !$("tab-home").contains(document.activeElement)) loadHome();
  }

  A.tab("home", { title: "Casa", init, load: loadHome, onState });
})();
