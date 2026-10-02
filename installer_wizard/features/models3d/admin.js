(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;

  const size = (n) => fmt.bytes(n || 0);
  const when = (t) => new Date(t * 1000).toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" });

  function render(d) {
    $("m3-count").textContent = d.models.length ? `(${d.models.length})` : "";
    const conv = Object.entries(d.converters || {}).filter(([, ok]) => !ok).map(([f]) => `.${f}`);
    $("m3-formats").textContent = `Formati: ${Object.keys(d.formats).map((f) => "." + f).join(" ")}` +
      (conv.length ? ` — per ${conv.join(" ")} serve la conversione sul server (Configurazione → JARVIS_3D_CONVERT)` : "");
    $("m3-list").innerHTML = d.models.map((m) => `<div class="m3-item" data-id="${fmt.esc(m.id)}">
        <div><b>🧊 ${fmt.esc(m.title)}</b> <span class="faint">${m.source === "ai" ? "creato da Jarvis" : "caricato"} · ${when(m.created)}</span>
          ${m.note ? `<div class="m3-note">${fmt.esc(m.note)}</div>` : ""}
          <div class="m3-files">${(m.files || []).map((f) => `<a href="/api/models3d/${encodeURIComponent(m.id)}/${encodeURIComponent(f.name)}">${fmt.esc(f.name)} <span class="faint">${size(f.size)}</span></a>`).join("")}</div></div>
        <div class="actions"><button class="btn sm primary" data-show>Mostra sul display</button><button class="btn sm danger" data-del>Elimina</button></div></div>`).join("")
      || '<div class="faint">Nessun modello: creane uno qui sopra o chiedi a Jarvis «creami un martello in 3D».</div>';
  }

  async function load() {
    try { render(await A.api("GET", "/api/models3d")); } catch (e) { $("m3-list").innerHTML = `<div class="faint">${fmt.esc(e.message)}</div>`; }
  }

  async function upload() {
    const files = [...$("m3-file").files];
    if (!files.length) return;
    let id = "";
    try {
      for (const f of files.sort((a, b) => /\.(mtl|bin|png|jpe?g)$/i.test(a.name) - /\.(mtl|bin|png|jpe?g)$/i.test(b.name))) {
        const r = await fetch(`/api/models3d/upload?name=${encodeURIComponent(f.name)}${id ? `&id=${encodeURIComponent(id)}` : ""}`,
          { method: "POST", headers: { "X-Jarvis-Request": "1" }, body: f, credentials: "same-origin" });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || `errore ${r.status}`);
        id = d.id;
      }
      A.toast("Caricato e aperto sul display"); $("m3-file").value = ""; load();
    } catch (e) { A.toast(e.message, true); }
  }

  function init() {
    $("m3-gen").addEventListener("submit", async (e) => {
      e.preventDefault();
      const subject = $("m3-subject").value.trim(); if (!subject) return;
      $("m3-gen-res").textContent = `Sto progettando «${subject}»… (può richiedere un minuto)`;
      try {
        const m = await A.api("POST", "/api/models3d/generate", { subject });
        $("m3-gen-res").textContent = `Fatto: ${m.title} (${(m.parts || []).length} parti) è sul display.`; load();
      } catch (err) { $("m3-gen-res").textContent = `⚠ ${err.message}`; }
    });
    $("m3-up").addEventListener("click", upload);
    $("m3-list").addEventListener("click", async (e) => {
      const item = e.target.closest("[data-id]"); if (!item) return;
      const url = `/api/models3d/${encodeURIComponent(item.dataset.id)}`;
      try {
        if (e.target.closest("[data-show]")) { await A.api("POST", `${url}/show`); A.toast("Aperto sul display"); }
        if (e.target.closest("[data-del]") && confirm("Eliminare il modello e i suoi file?")) { await A.api("DELETE", url); load(); }
      } catch (err) { A.toast(err.message, true); }
    });
  }

  A.tab("models3d", { title: "Modelli 3D", init, load });
})();
