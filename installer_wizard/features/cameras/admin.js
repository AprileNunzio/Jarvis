(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  const KIND = { rtsp: "RTSP", onvif: "ONVIF", hikvision: "Hikvision", webcam: "Webcam" };

  function row(c) {
    const rec = c.recording;
    return `<div class="cam-item" data-id="${fmt.esc(c.id)}">
      <div class="cam-dot ${rec ? "on" : ""}" title="${rec ? "sta registrando" : "non registra"}"></div>
      <div style="flex:1">
        <div class="nm">${fmt.esc(c.name)} <span class="faint">· ${fmt.esc(KIND[c.kind] || c.kind)}${c.node ? ` · ${fmt.esc(c.node)}` : ""}</span></div>
        <div class="cam-ctrl">
          <label class="switch"><input type="checkbox" data-f="enabled" ${c.enabled ? "checked" : ""}> attiva</label>
          <label class="switch"><input type="checkbox" data-f="consent" ${c.consent ? "checked" : ""}> consenso a riprendere</label>
          <label class="switch"><input type="checkbox" data-f="record" ${c.record ? "checked" : ""}> registra</label>
          <select data-f="retention_min">${[5, 15, 60].map((m) => `<option value="${m}" ${c.retention_min === m ? "selected" : ""}>${m === 60 ? "1 ora" : m + " min"}</option>`).join("")}</select>
          <button class="btn sm danger" data-del>Elimina</button>
        </div>
        ${c.record && c.enabled && !c.consent ? '<div class="cam-warn">Serve il consenso per registrare.</div>' : ""}
      </div></div>`;
  }

  async function load() {
    let d;
    try { d = await A.api("GET", "/api/cameras"); } catch (e) { A.toast(e.message, true); return; }
    $("cam-list").innerHTML = d.cameras.length ? d.cameras.map(row).join("")
      : '<div class="faint">Nessuna telecamera. Aggiungine una qui sopra.</div>';
  }

  function init() {
    $("cam-add").addEventListener("submit", async (e) => {
      e.preventDefault();
      const body = { name: $("cam-name").value.trim(), kind: $("cam-kind").value, url: $("cam-url").value.trim(),
        node: $("cam-node").value.trim(), retention_min: parseInt($("cam-ret").value, 10) };
      if (!body.name) return;
      try { await A.api("POST", "/api/cameras", body); $("cam-name").value = ""; $("cam-url").value = ""; $("cam-node").value = ""; load(); }
      catch (err) { A.toast(err.message, true); }
    });
    $("cam-list").addEventListener("change", async (e) => {
      const item = e.target.closest(".cam-item"); if (!item || !e.target.dataset.f) return;
      const val = e.target.type === "checkbox" ? e.target.checked : (e.target.dataset.f === "retention_min" ? parseInt(e.target.value, 10) : e.target.value);
      try { await A.api("PUT", `/api/cameras/${encodeURIComponent(item.dataset.id)}`, { [e.target.dataset.f]: val }); load(); }
      catch (err) { A.toast(err.message, true); load(); }
    });
    $("cam-list").addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-del]"); if (!btn) return;
      const item = btn.closest(".cam-item");
      if (!confirm("Eliminare questa telecamera e fermare la registrazione?")) return;
      try { await A.api("DELETE", `/api/cameras/${encodeURIComponent(item.dataset.id)}`); load(); }
      catch (err) { A.toast(err.message, true); }
    });
  }

  A.tab("cameras", { title: "Telecamere", init, load });
})();
