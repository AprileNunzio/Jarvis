(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  let netData = { devices: [], types: {} }, netSel = null;

  async function loadNetwork() {
    try { netData = await A.api("GET", "/api/network"); } catch (e) { A.toast(e.message, true); return; }
    const online = netData.devices.filter((d) => d.online).length;
    $("net-info").textContent = `${netData.subnet || "rete non rilevata"} · gateway ${netData.gateway || "—"} · ${online} connessi su ${netData.devices.length} conosciuti · ultima scansione ${netData.last_scan ? new Date(netData.last_scan * 1000).toLocaleTimeString("it-IT") : "mai"}${netData.scanning ? " · scansione in corso…" : ""}`;
    renderNetwork();
    if (netSel) showDevice(netSel);
  }

  function renderNetwork() {
    const q = ($("net-filter").value || "").toLowerCase();
    $("net-body").innerHTML = netData.devices.filter((d) => !q || JSON.stringify([d.label, d.ip, d.vendor, d.type_label, d.room]).toLowerCase().includes(q)).map((d) => `
      <tr data-key="${fmt.esc(d.key)}" style="cursor:pointer">
        <td><span class="dot ${d.online ? "ok" : "idle"}"></span></td>
        <td>${d.icon} ${fmt.esc(d.label)}${d.room ? `<div class="faint" style="font-size:11px">${fmt.esc(d.room)}</div>` : ""}</td>
        <td class="mono">${fmt.esc(d.ip || "")}</td>
        <td style="font-size:12px">${fmt.esc(d.vendor || "—")}<div class="faint mono">${fmt.esc(d.mac || "")}</div></td>
        <td style="font-size:12px">${fmt.esc(d.type_label)}</td>
        <td class="mono">${(d.ports || []).length || (d.studied ? 0 : "…")}</td>
        <td style="font-size:12px" class="dim">${fmt.esc(d.habits)}</td>
        <td style="text-align:right"><button class="btn sm" data-study="${fmt.esc(d.key)}">Studia</button></td></tr>`).join("")
      || '<tr><td colspan="8" class="faint">Nessun dispositivo ancora: avvia una scansione.</td></tr>';
  }

  function showDevice(key) {
    const d = netData.devices.find((x) => x.key === key); if (!d) return;
    netSel = key;
    const panel = $("net-detail"); panel.style.display = "block";
    panel.innerHTML = `<div class="panel-title">${d.icon} ${fmt.esc(d.label)}</div>
      <div class="form-grid" style="margin-bottom:16px">
        <div><label>Nome</label><input data-nk="name" value="${fmt.esc(d.name || "")}" placeholder="${fmt.esc(d.label)}"></div>
        <div><label>Stanza</label><input data-nk="room" value="${fmt.esc(d.room || "")}"></div>
        <div><label>Proprietario</label><input data-nk="owner" value="${fmt.esc(d.owner || "")}"></div>
        <div><label>Tipo</label><select data-nk="type">${Object.entries(netData.types).map(([k, v]) => `<option value="${k}" ${k === d.type ? "selected" : ""}>${fmt.esc(v)}</option>`).join("")}</select></div>
        <div class="wide"><label>Note</label><input data-nk="notes" value="${fmt.esc(d.notes || "")}"></div>
        <div><label class="row" style="gap:8px;margin:0"><input type="checkbox" data-nk="trusted" style="width:auto" ${d.trusted ? "checked" : ""}> Dispositivo fidato</label></div>
      </div>
      <table><tbody>
        <tr><td class="dim">Hostname</td><td class="mono">${fmt.esc(d.hostname || "—")}</td></tr>
        <tr><td class="dim">Sistema operativo</td><td>${fmt.esc(d.os || "—")}</td></tr>
        <tr><td class="dim">Pagina web</td><td>${fmt.esc(d.web_title || "—")}</td></tr>
        <tr><td class="dim">Servizi mDNS</td><td class="mono">${fmt.esc((d.mdns || []).join(", ") || "—")}</td></tr>
        <tr><td class="dim">Porte aperte</td><td class="mono">${(d.ports || []).map((p) => `${p.port}/${fmt.esc(p.service)}${p.product ? " (" + fmt.esc(p.product) + ")" : ""}`).join("<br>") || "—"}</td></tr>
        <tr><td class="dim">Visto la prima volta</td><td>${d.first_seen ? new Date(d.first_seen * 1000).toLocaleString("it-IT") : "—"}</td></tr>
        <tr><td class="dim">Ultimo studio</td><td>${d.studied ? new Date(d.studied * 1000).toLocaleString("it-IT") : "in coda"}</td></tr>
      </tbody></table>`;
  }

  function init() {
    $("net-body").addEventListener("click", async (e) => {
      const key = e.target.dataset.study;
      if (key) { try { await A.api("POST", `/api/network/study/${encodeURIComponent(key)}`); A.toast("Studio del dispositivo avviato (fino a qualche minuto)"); } catch (err) { A.toast(err.message, true); } return; }
      const row = e.target.closest("tr[data-key]"); if (row) showDevice(row.dataset.key);
    });
    $("net-detail").addEventListener("change", async (e) => {
      const k = e.target.dataset.nk; if (!k || !netSel) return;
      try { await A.api("PUT", `/api/network/devices/${encodeURIComponent(netSel)}`, { [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }); A.toast("Salvato"); loadNetwork(); }
      catch (err) { A.toast(err.message, true); }
    });
    $("net-filter").addEventListener("input", renderNetwork);
    $("net-scan").addEventListener("click", async () => {
      try { await A.api("POST", "/api/network/scan"); A.toast("Scansione avviata"); setTimeout(loadNetwork, 3000); setTimeout(loadNetwork, 20000); } catch (e) { A.toast(e.message, true); }
    });
  }

  A.tab("network", { title: "Rete", init, load: loadNetwork });
})();
