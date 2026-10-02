(() => {
  const A = window.JarvisAdmin, { $, fmt } = A;
  let widgetData = null;

  const whenText = (w) => w.bind ? `quando c'è ${fmt.esc(typeof w.bind === "string" ? w.bind : w.bind.attr)}`
    : w.intents.length ? `dopo una domanda (${w.intents.map(fmt.esc).join(", ")})${w.ttl ? `, per ${Math.round(w.ttl / 60)} min` : ""}`
    : "quando un modulo o un sensore lo richiede";

  async function loadWidgets() {
    try { widgetData = await A.api("GET", "/api/widgets"); } catch (e) { A.toast(e.message, true); return; }
    renderWidgets();
  }

  function renderWidgets() {
    const d = widgetData;
    $("wd-active").innerHTML = d.active.map((i) => `<span>${fmt.esc(i.icon)} ${fmt.esc(i.name)} · ${i.priority} <button class="btn sm" data-wdhide="${fmt.esc(i.key)}" title="Nascondi">✕</button></span>`).join("") || '<span class="faint">Nessun widget: solo il volto.</span>';
    $("wd-body").innerHTML = d.widgets.map((w) => `<tr><td style="font-size:20px">${fmt.esc(w.icon)}</td>
      <td>${fmt.esc(w.name)} ${w.source !== "system" ? `<span class="badge">${w.source === "ai" ? "creato da Jarvis" : "aggiunto da te"}</span>` : ""}<div class="faint" style="font-size:12px">${fmt.esc(w.description)}</div></td>
      <td style="font-size:12px" class="dim">${whenText(w)}${w.size === "full" ? " · schermo intero" : ""}</td>
      <td><input type="number" min="0" max="100" value="${w.effective_priority}" data-wdprio="${fmt.esc(w.id)}" style="width:76px"></td>
      <td><input type="checkbox" style="width:auto" data-wdon="${fmt.esc(w.id)}" ${w.enabled ? "checked" : ""}></td>
      <td style="text-align:right"><button class="btn sm" data-wdtest="${fmt.esc(w.id)}">Prova</button></td></tr>`).join("");
    $("wd-note").innerHTML = `Nuovi widget: una cartella con <span class="mono">widget.json</span> e <span class="mono">widget.js</span> in <span class="mono">installer_wizard/widgets</span> o <span class="mono">${fmt.esc(d.user_dir)}</span>, rilevata entro 20 secondi.`
      + (d.errors.length ? `<div style="color:var(--amber)">Non validi: ${d.errors.map((e) => `${fmt.esc(e.path)} (${fmt.esc(e.error)})`).join("; ")}</div>` : "");
  }

  function init() {
    $("tab-widgets").addEventListener("change", async (e) => {
      const t = e.target, id = t.dataset.wdprio || t.dataset.wdon; if (!id) return;
      try { widgetData = await A.api("PUT", `/api/widgets/${encodeURIComponent(id)}`, t.dataset.wdprio ? { priority: t.value } : { enabled: t.checked }); renderWidgets(); A.toast("Salvato"); }
      catch (err) { A.toast(err.message, true); }
    });
    $("tab-widgets").addEventListener("click", async (e) => {
      const t = e.target.closest("button"); if (!t) return;
      try {
        if (t.dataset.wdtest) { widgetData = await A.api("POST", `/api/widgets/${encodeURIComponent(t.dataset.wdtest)}/test`); A.toast("Widget di prova sul display per 20-30 secondi"); }
        else if (t.dataset.wdhide) widgetData = await A.api("DELETE", `/api/desk/${encodeURIComponent(t.dataset.wdhide)}`);
        else return;
        renderWidgets();
      } catch (err) { A.toast(err.message, true); }
    });
  }

  A.tab("widgets", { title: "Widget", init, load: loadWidgets });
})();
