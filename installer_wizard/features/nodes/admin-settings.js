(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  let current = null;

  function row(it) {
    return `<label class="ns-row ${it.custom ? "on" : ""}" data-key="${fmt.esc(it.key)}">
      <input type="checkbox" data-own ${it.custom ? "checked" : ""} title="Personalizza per questo nodo">
      <span class="ns-label">${fmt.esc(it.label)}<small class="mono">${fmt.esc(it.key)}</small></span>
      <input data-val value="${fmt.esc(it.custom ? it.value : "")}" placeholder="globale: ${fmt.esc(it.global || "(vuoto)")}" ${it.custom ? "" : "disabled"}></label>`;
  }

  function render(d) {
    const box = $("nd-settings"), own = d.items.filter((i) => i.custom).length;
    box.hidden = false;
    box.innerHTML = `<div class="nd-head"><div class="panel-title" style="margin:0">⚙ Impostazioni di ${fmt.esc(d.node.name)}
        <span class="faint">${own ? `${own} personalizzate, il resto segue le globali` : "segue tutte le impostazioni globali"}</span></div>
        <div class="actions"><button class="btn sm" data-ns="copy">Personalizza tutto (copia le globali)</button>
          <button class="btn sm" data-ns="reset">Torna alle globali</button><button class="btn sm" data-ns="close">Chiudi</button></div></div>
      <input class="ns-filter" placeholder="Cerca un'impostazione…" data-ns-filter>
      <div class="ns-list">${d.items.map(row).join("")}</div>
      <div class="actions" style="margin-top:12px"><button class="btn primary" data-ns="save">Salva le preferenze del nodo</button></div>`;
    box.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function open(id) {
    current = id;
    try { render(await A.api("GET", `/api/nodes/${encodeURIComponent(id)}/settings`)); } catch (e) { A.toast(e.message, true); }
  }

  async function send(settings, note) {
    try {
      await A.api("PUT", `/api/nodes/${encodeURIComponent(current)}`, { settings });
      A.toast(note); open(current);
    } catch (e) { A.toast(e.message, true); }
  }

  function collect() {
    const out = {};
    $("nd-settings").querySelectorAll(".ns-row").forEach((r) => {
      out[r.dataset.key] = r.querySelector("[data-own]").checked ? r.querySelector("[data-val]").value.trim() : "";
    });
    return out;
  }

  document.addEventListener("click", (e) => {
    const b = e.target.closest("#nd-settings [data-ns]");
    if (!b) return;
    const act = b.dataset.ns;
    if (act === "close") { $("nd-settings").hidden = true; current = null; }
    else if (act === "copy") send("copy_all", "Tutte le impostazioni copiate: ora puoi cambiarle solo per questo nodo");
    else if (act === "reset" && confirm("Il nodo torna a seguire tutte le impostazioni globali?")) send("reset", "Il nodo segue le impostazioni globali");
    else if (act === "save") send(collect(), "Preferenze del nodo salvate: valgono dal prossimo contatto (entro 30 secondi)");
  });
  document.addEventListener("change", (e) => {
    const own = e.target.closest("#nd-settings [data-own]");
    if (!own) return;
    const r = own.closest(".ns-row"), val = r.querySelector("[data-val]");
    val.disabled = !own.checked; r.classList.toggle("on", own.checked);
    if (own.checked && !val.value) { val.value = val.placeholder.replace(/^globale: /, "").replace("(vuoto)", ""); val.focus(); }
  });
  document.addEventListener("input", (e) => {
    if (!e.target.matches("#nd-settings [data-ns-filter]")) return;
    const q = e.target.value.toLowerCase();
    $("nd-settings").querySelectorAll(".ns-row").forEach((r) => { r.hidden = q && !r.textContent.toLowerCase().includes(q); });
  });

  A.nodeSettings = { open };
})();
